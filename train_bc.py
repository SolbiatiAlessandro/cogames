"""Train TutorialPolicyNet via behavioral cloning from scripted agent.

Step 1: Collect data from scripted aligner agent
Step 2: Train CNN+LSTM to predict expert actions
Step 3: Save model for RL fine-tuning

Usage:
  python train_bc.py [num_episodes] [num_epochs] [batch_size]
"""
import sys
import os
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), "src")))

from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.cog import CogTeam
from cogames.cogs_vs_clips.variants import NoVibesVariant, NoClipsVariant
from mettagrid.simulator.simulator import Simulation
from mettagrid.policy.policy import PolicySpec
from mettagrid.policy.loader import initialize_or_load_policy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from cogames.policy.tutorial_policy import TutorialPolicyNet

NUM_COLLECTION_EPISODES = int(sys.argv[1]) if len(sys.argv) > 1 else 5
NUM_BC_EPOCHS = int(sys.argv[2]) if len(sys.argv) > 2 else 50
BATCH_SIZE = int(sys.argv[3]) if len(sys.argv) > 3 else 256
MAX_STEPS = 3000

# Map expert action names to 5-action space
MOVE_MAP = {
    "noop": 0, "move_north": 1, "move_south": 2, "move_west": 3, "move_east": 4,
}

# ── Step 1: Collect data ──
print("=== Step 1: Collecting expert data ===")

competition_basic = None
for m in MISSIONS:
    if getattr(m, 'name', '') == 'basic':
        site = getattr(m, 'site', None)
        if site and getattr(site, 'name', '') == 'cogsguard_machina_1':
            competition_basic = m
            break

competition_basic.max_steps = MAX_STEPS
competition_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1, initial_hearts=200),
}
no_vibes = NoVibesVariant()
no_clips = NoClipsVariant()
competition_basic.variants = [no_vibes, no_clips]
config = competition_basic.make_env()
config.game.map_builder.seed = 42

# Aligner-only gear
for station_name in ["c:scrambler", "c:miner", "c:scout"]:
    if station_name in config.game.objects:
        station = config.game.objects[station_name]
        if "change_gear" in station.on_use_handlers:
            del station.on_use_handlers["change_gear"]

env_interface = PolicyEnvInterface.from_mg_cfg(config)
obs_shape = env_interface.observation_space.shape

expert_spec = PolicySpec(
    class_path="cogames.policy.machina_roles_policy.MachinaRolesPolicy",
    kwargs={"num_aligners": 8, "aligner_ids": "0,1,2,3,4,5,6,7"},
)

all_obs = []
all_actions = []

for ep in range(NUM_COLLECTION_EPISODES):
    expert_policy = initialize_or_load_policy(env_interface, expert_spec)
    sim = Simulation(config, seed=42 + ep)
    expert_policy.reset()
    agents = sim.agents()

    for step in range(MAX_STEPS):
        if sim.is_done():
            break
        for i, agent in enumerate(agents):
            obs = agent.observation
            obs_array = np.full(obs_shape, 255, dtype=np.uint8)
            for j, token in enumerate(obs.tokens[:obs_shape[0]]):
                obs_array[j, 0] = token.raw_token[0]
                obs_array[j, 1] = token.raw_token[1]
                if obs_shape[1] > 2:
                    obs_array[j, 2] = token.raw_token[2]
            ap = expert_policy.agent_policy(i)
            action = ap.step(obs)
            action_name = action.name if hasattr(action, 'name') else str(action)
            action_idx = MOVE_MAP.get(action_name, 0)
            all_obs.append(obs_array)
            all_actions.append(action_idx)
            agent.set_action(action)
        sim.step()

    stats = sim.episode_stats
    game = stats.get('game', {})
    aligned = game.get('cogs/aligned.junction.held', 0)
    print(f"  Episode {ep+1}/{NUM_COLLECTION_EPISODES}: {len(all_obs)-(ep*MAX_STEPS*8)} samples, aligned={aligned:.0f}")
    sim.close()

obs_data = np.array(all_obs, dtype=np.uint8)
actions_data = np.array(all_actions, dtype=np.int64)
print(f"  Total: {len(all_obs)} samples, shape={obs_data.shape}")
action_dist = dict(zip(*np.unique(actions_data, return_counts=True)))
print(f"  Actions: {action_dist}")


# ── Step 2: Train ──
print("\n=== Step 2: Training behavioral cloning ===")

class BCDataset(Dataset):
    def __init__(self, obs, actions):
        self.obs = torch.from_numpy(obs)
        self.actions = torch.from_numpy(actions)

    def __len__(self):
        return len(self.actions)

    def __getitem__(self, idx):
        return self.obs[idx], self.actions[idx]

dataset = BCDataset(obs_data, actions_data)
loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, drop_last=True)

net = TutorialPolicyNet(env_interface)
optimizer = torch.optim.Adam(net.parameters(), lr=1e-3)
criterion = nn.CrossEntropyLoss()

best_loss = float('inf')
for epoch in range(NUM_BC_EPOCHS):
    total_loss = 0
    correct = 0
    total = 0
    net.train()
    for batch_obs, batch_actions in loader:
        logits, _ = net(batch_obs.unsqueeze(1))
        loss = criterion(logits, batch_actions)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
        correct += (logits.argmax(dim=-1) == batch_actions).sum().item()
        total += len(batch_actions)

    avg_loss = total_loss / len(loader)
    accuracy = correct / total * 100
    if epoch % 5 == 0 or epoch == NUM_BC_EPOCHS - 1:
        print(f"  Epoch {epoch+1}/{NUM_BC_EPOCHS}: loss={avg_loss:.4f}, accuracy={accuracy:.1f}%")

    if avg_loss < best_loss:
        best_loss = avg_loss
        os.makedirs("bc_models", exist_ok=True)
        torch.save(net.state_dict(), "bc_models/bc_best.pt")

print(f"\n  Best loss: {best_loss:.4f}")
print(f"  Model saved to bc_models/bc_best.pt")

# ── Step 3: Eval ──
print("\n=== Step 3: Quick evaluation ===")
net.eval()
with torch.no_grad():
    sample_obs = torch.from_numpy(obs_data[:100]).unsqueeze(1)
    logits, _ = net(sample_obs)
    probs = torch.softmax(logits, dim=-1)
    pred_actions = logits.argmax(dim=-1).numpy()
    true_actions = actions_data[:100]
    accuracy = (pred_actions == true_actions).mean() * 100
    print(f"  Sample accuracy: {accuracy:.1f}%")
    print(f"  Avg action probs: {probs.mean(dim=0).numpy()}")
