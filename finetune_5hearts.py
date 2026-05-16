"""Fine-tune the 15-hearts model on 5-hearts (default competition) settings.

Loads model weights AND optimizer state from the 15-hearts epoch 20 checkpoint
to avoid catastrophic forgetting. The optimizer's learned momentum/variance
preserves knowledge while the model adapts to fewer initial hearts.
"""
import os
import sys
import torch
import pufferlib.pufferl as pufferl
import pufferlib.vector as pvector

from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
from cogames.cogs_vs_clips.cog import CogTeam
from cogames.cogs_vs_clips.variants import NoVibesVariant
from cogames.train import initialize_or_load_policy

from mettagrid.config.game_value import stat
from mettagrid.config.reward_config import Aggregation, reward
from mettagrid.policy.policy import PolicySpec
from mettagrid.policy.policy_env_interface import PolicyEnvInterface

_MINER_ELEMENTS = ("carbon", "oxygen", "germanium", "silicon")

CHECKPOINT_DIR = "train_dir_5act/177889060032"
MODEL_PATH = os.path.join(CHECKPOINT_DIR, "model_000020.pt")
TRAINER_STATE_PATH = os.path.join(CHECKPOINT_DIR, "trainer_state.pt")
OUTPUT_DIR = "train_dir_finetune_5h"

competition_basic = None
for m in MISSIONS:
    if getattr(m, 'name', '') == 'basic':
        site = getattr(m, 'site', None)
        if site and getattr(site, 'name', '') == 'cogsguard_machina_1':
            competition_basic = m
            break

if competition_basic is None:
    raise ValueError("Could not find cogsguard_machina_1.basic mission")

competition_basic.max_steps = 1000
competition_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1),
}

no_vibes = NoVibesVariant()
competition_basic.variants = list(getattr(competition_basic, 'variants', []))
competition_basic.variants.append(no_vibes)

config = competition_basic.make_env()

apply_reward_variants(config, variants=["milestones_2", "credit"])

for agent_cfg in config.game.agents:
    rewards = dict(agent_cfg.rewards)
    rewards["deposit_diversity"] = reward(
        [stat(f"{e}.lost") for e in _MINER_ELEMENTS],
        aggregation=Aggregation.SUM_LOGS,
        weight=0.15,
        max=2.0,
    )
    rewards["mining_diversity"] = reward(
        [stat(f"{e}.gained") for e in _MINER_ELEMENTS],
        aggregation=Aggregation.SUM_LOGS,
        weight=0.1,
        max=1.5,
    )
    rewards["aligner_gear_bonus"] = reward(
        stat("aligner.gained"),
        weight=0.5,
    )
    rewards["alignment_bonus"] = reward(
        stat("junction.aligned_by_agent"),
        weight=1.0,
    )
    agent_cfg.rewards = rewards


def make_env():
    return config


if __name__ == "__main__":
    device = torch.device("cpu")

    vecenv = pvector.make(
        "cogames.cogs_vs_clips",
        env_kwargs={"env_cfg": config},
        num_envs=256,
        backend=pvector.Multiprocessing,
    )

    policy = initialize_or_load_policy(
        PolicyEnvInterface.from_mg_cfg(vecenv.driver_env.env_cfg),
        PolicySpec(
            class_path="cogames.policy.tutorial_policy.TutorialPolicy",
            data_path=MODEL_PATH,
        ),
    )
    network = policy.network()
    network.to(device)

    train_args = dict(
        env="cogames.cogs_vs_clips",
        device="cpu",
        total_timesteps=5000000,
        minibatch_size=4096,
        batch_size="auto",
        data_dir=OUTPUT_DIR,
        checkpoint_interval=5,
        bptt_horizon=64,
        seed=42,
        use_rnn=True,
        torch_deterministic=True,
        cpu_offload=False,
        optimizer="adam",
        anneal_lr=True,
        precision="float32",
        learning_rate=0.00046,  # half the normal LR for fine-tuning
        gamma=0.995,
        gae_lambda=0.90,
        update_epochs=1,
        clip_coef=0.1,  # tighter clipping for fine-tuning
        vf_coef=2.0,
        vf_clip_coef=0.1,  # tighter value clipping
        max_grad_norm=1.0,  # tighter gradient clipping
        ent_coef=0.005,  # lower entropy for exploitation
        adam_beta1=0.95,
        adam_beta2=0.999,
        adam_eps=1e-8,
        max_minibatch_size=32768,
        compile=False,
        vtrace_rho_clip=1.0,
        vtrace_c_clip=1.0,
        prio_alpha=0.8,
        prio_beta0=0.2,
        min_lr_ratio=0.0,
    )

    trainer = pufferl.PuffeRL(train_args, vecenv, network)

    # Load optimizer state from the 15-hearts training
    if os.path.exists(TRAINER_STATE_PATH):
        print(f"Loading optimizer state from {TRAINER_STATE_PATH}")
        state = torch.load(TRAINER_STATE_PATH, map_location=device)
        try:
            trainer.optimizer.load_state_dict(state["optimizer_state_dict"])
            print(f"Optimizer state loaded (from epoch {state.get('update', '?')})")
        except Exception as e:
            print(f"Warning: Could not load optimizer state: {e}")
            print("Continuing with fresh optimizer")
    else:
        print(f"Warning: {TRAINER_STATE_PATH} not found, using fresh optimizer")

    print(f"Starting fine-tuning: 5 hearts (competition default), LR=0.00046, clip=0.1")

    try:
        while trainer.global_step < train_args["total_timesteps"]:
            trainer.evaluate()
            trainer.train()
    except KeyboardInterrupt:
        print("Training interrupted")

    trainer.close()
    print(f"Checkpoints saved to {OUTPUT_DIR}")
