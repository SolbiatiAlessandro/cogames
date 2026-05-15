"""RL training script with CNN+LSTM and reward shaping for cogames competition.

Based on tutorials/TRAIN_ALIGNER.py but adapted for the competition mission.
"""
import sys
import torch
import torch.nn as nn
from einops import rearrange

import pufferlib.vector as pvector
from cogames.cogs_vs_clips.clip_difficulty import EASY
from cogames.cogs_vs_clips.cog import CogConfig, CogTeam
from cogames.cogs_vs_clips.mission import CvCMission
from cogames.cogs_vs_clips.sites import COGSGUARD_ARENA
from cogames.cogs_vs_clips.tutorials.aligner_tutorial import AlignerRewardsVariant
from mettagrid import MettaGridConfig
from mettagrid.envs.early_reset_handler import EarlyResetHandler
from mettagrid.envs.stats_tracker import StatsTracker
from mettagrid.mapgen.mapgen import MapGen
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Simulator
from mettagrid.util.stats_writer import NoopStatsWriter
from pufferlib import pufferl
from pufferlib.pufferlib import set_buffers

NUM_AGENTS = 8
MAX_STEPS = 3000
SEED = 42
TOTAL_TIMESTEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000_000

DEVICE = torch.device("cpu")

mission = CvCMission(
    name="rl_training",
    description="RL training with reward shaping on arena",
    site=COGSGUARD_ARENA,
    num_cogs=NUM_AGENTS,
    max_steps=MAX_STEPS,
    cog=CogConfig(heart_limit=3),
    teams={"cogs": CogTeam(name="cogs", num_agents=NUM_AGENTS, wealth=3, initial_hearts=120)},
    variants=[EASY, AlignerRewardsVariant()],
)

env_cfg: MettaGridConfig = mission.make_env()


def tokens_to_grid(observations, obs_height, obs_width, num_features, feature_scale):
    batch_size = observations.shape[0]
    device = observations.device
    coords_byte = observations[..., 0].to(torch.long)
    x_coords = coords_byte & 0x0F
    y_coords = (coords_byte >> 4) & 0x0F
    feature_ids = observations[..., 1].to(torch.long)
    values = observations[..., 2].to(torch.float32)
    valid_mask = (observations[..., 0] != 0xFF).float()
    x_coords = torch.clamp(x_coords, 0, obs_width - 1)
    y_coords = torch.clamp(y_coords, 0, obs_height - 1)
    feature_ids_clamped = torch.clamp(feature_ids, 0, num_features - 1)
    scale = feature_scale[torch.clamp(feature_ids, 0, feature_scale.shape[0] - 1)]
    values = (values / (scale + 1e-6)) * valid_mask
    grid = torch.zeros(batch_size, num_features, obs_height, obs_width, device=device)
    batch_idx = torch.arange(batch_size, device=device).unsqueeze(1).expand_as(x_coords)
    linear_idx = (
        batch_idx * (num_features * obs_height * obs_width)
        + feature_ids_clamped * (obs_height * obs_width)
        + y_coords * obs_width
        + x_coords
    )
    grid.view(-1).scatter_add_(0, linear_idx.view(-1), values.view(-1))
    return grid


class CogsPolicyNet(nn.Module):
    _feature_scale: torch.Tensor

    def __init__(self, env_info: PolicyEnvInterface):
        super().__init__()
        self.hidden_size = 256
        self._obs_height = env_info.obs_height
        self._obs_width = env_info.obs_width
        self._num_features = max((int(f.id) for f in env_info.obs_features), default=0) + 1

        feature_norms = {f.id: f.normalization for f in env_info.obs_features}
        max_id = max((int(fid) for fid in feature_norms.keys()), default=-1)
        feature_scale = torch.ones(max(256, max_id + 1), dtype=torch.float32)
        for fid, norm in feature_norms.items():
            feature_scale[fid] = max(float(norm), 1.0)
        self.register_buffer("_feature_scale", feature_scale)

        self._cnn = nn.Sequential(
            nn.Conv2d(self._num_features, 32, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.Flatten(),
        )
        with torch.no_grad():
            dummy = torch.zeros(1, self._num_features, self._obs_height, self._obs_width)
            cnn_out_size = self._cnn(dummy).shape[1]

        self._cnn_fc = nn.Linear(cnn_out_size, 128)
        self._self_encoder = nn.Linear(self._num_features, 128)
        self._rnn = nn.LSTM(self.hidden_size, self.hidden_size, num_layers=1, batch_first=True)

        num_actions = len(env_info.action_names)
        self._action_head = nn.Linear(self.hidden_size, num_actions)
        self._value_head = nn.Linear(self.hidden_size, 1)

    def forward(self, observations, state=None):
        orig_shape = observations.shape
        if observations.dim() == 4:
            segments, bptt_horizon = orig_shape[0], orig_shape[1]
            observations = observations.reshape(segments * bptt_horizon, *orig_shape[2:])
        else:
            segments, bptt_horizon = orig_shape[0], 1

        grid = tokens_to_grid(observations, self._obs_height, self._obs_width, self._num_features, self._feature_scale)
        cnn_out = torch.relu(self._cnn_fc(self._cnn(grid)))
        center = grid[:, :, self._obs_height // 2, self._obs_width // 2]
        self_out = torch.relu(self._self_encoder(center))

        hidden = torch.cat([cnn_out, self_out], dim=-1)
        hidden = rearrange(hidden, "(b t) h -> b t h", t=bptt_horizon, b=segments)

        rnn_state = None
        if state is not None:
            h, c = state.get("lstm_h"), state.get("lstm_c")
            if h is not None and c is not None:
                h = h.transpose(0, 1) if h.dim() == 3 else h.unsqueeze(0)
                c = c.transpose(0, 1) if c.dim() == 3 else c.unsqueeze(0)
                rnn_state = (h, c)

        hidden, (h_out, c_out) = self._rnn(hidden, rnn_state)

        if state is not None and "lstm_h" in state:
            state["lstm_h"] = h_out.transpose(0, 1)
            state["lstm_c"] = c_out.transpose(0, 1)

        hidden = rearrange(hidden, "b t h -> (b t) h")
        return self._action_head(hidden), self._value_head(hidden)

    forward_eval = forward


def make_env(cfg=None, buf=None, seed=None):
    target_cfg = env_cfg.model_copy(deep=True)
    map_builder = target_cfg.game.map_builder
    if isinstance(map_builder, MapGen.Config) and seed is not None:
        map_builder.seed = SEED + seed
    simulator = Simulator()
    simulator.add_event_handler(StatsTracker(NoopStatsWriter()))
    simulator.add_event_handler(EarlyResetHandler())
    from mettagrid import PufferMettaGridEnv
    env = PufferMettaGridEnv(simulator, target_cfg, buf=buf, seed=seed or 0)
    set_buffers(env, buf)
    return env


NUM_ENVS = 4
vecenv = pvector.make(
    make_env,
    num_envs=NUM_ENVS,
    num_workers=1,
    batch_size=NUM_ENVS,
    backend=pvector.Serial,
)

policy_env_info = PolicyEnvInterface.from_mg_cfg(vecenv.driver_env.env_cfg)
net = CogsPolicyNet(policy_env_info).to(DEVICE)

total_params = sum(p.numel() for p in net.parameters())
print(f"CNN+LSTM parameters: {total_params:,}")
print(f"Obs grid: {policy_env_info.obs_height}x{policy_env_info.obs_width}")
print(f"Actions: {policy_env_info.action_names}")

total_agents = vecenv.num_agents
BPTT_HORIZON = 64
BATCH_SIZE = max(4096, total_agents * BPTT_HORIZON)
MINIBATCH_SIZE = min(4096, BATCH_SIZE)

train_config = dict(
    env="cogames.cogs_vs_clips",
    device=DEVICE.type,
    total_timesteps=max(TOTAL_TIMESTEPS, BATCH_SIZE),
    batch_size=BATCH_SIZE,
    minibatch_size=MINIBATCH_SIZE,
    bptt_horizon=BPTT_HORIZON,
    seed=SEED,
    use_rnn=True,
    torch_deterministic=True,
    cpu_offload=False,
    compile=False,
    optimizer="adam",
    learning_rate=0.00092,
    anneal_lr=True,
    min_lr_ratio=0.0,
    adam_beta1=0.95,
    adam_beta2=0.999,
    adam_eps=1e-8,
    precision="float32",
    gamma=0.995,
    gae_lambda=0.90,
    update_epochs=1,
    clip_coef=0.2,
    vf_coef=2.0,
    vf_clip_coef=0.2,
    max_grad_norm=1.5,
    ent_coef=0.01,
    vtrace_rho_clip=1.0,
    vtrace_c_clip=1.0,
    prio_alpha=0.8,
    prio_beta0=0.2,
    data_dir="./train_dir_cnn",
    checkpoint_interval=25,
    max_minibatch_size=32768,
)

print(f"\nTraining for {TOTAL_TIMESTEPS:,} steps...")
trainer = pufferl.PuffeRL(train_config, vecenv, net)
print(f"Batch size: {trainer.config['batch_size']}, Total epochs: {trainer.total_epochs}")

epoch = 0
try:
    while trainer.global_step < TOTAL_TIMESTEPS:
        eval_stats = trainer.evaluate()
        train_stats = trainer.train()
        epoch += 1
        if epoch % 5 == 0:
            reward_mean = eval_stats.get("reward_mean", 0) if eval_stats else 0
            print(f"Epoch {epoch} | Step {trainer.global_step:,} | Reward: {reward_mean:.4f}")
except KeyboardInterrupt:
    print(f"Interrupted at epoch {epoch}")

trainer.print_dashboard()
trainer.close()

import pathlib
run_dir = pathlib.Path("train_dir_cnn") / trainer.logger.run_id
checkpoints = sorted(run_dir.glob("model_*.pt"), key=lambda p: p.stat().st_mtime)
if checkpoints:
    print(f"\nFinal checkpoint: {checkpoints[-1]}")
    torch.save(net.state_dict(), run_dir / "final_net.pt")
    print(f"Network state saved: {run_dir / 'final_net.pt'}")
print("Done!")
