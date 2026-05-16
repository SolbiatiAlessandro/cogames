"""Diagnose RL model behavior on competition map.

Runs a single episode and tracks per-agent stats to understand
what the model actually does (stays at hub? explores? gets gear?).
"""
import sys
import torch
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.cog import CogTeam
from cogames.cogs_vs_clips.variants import NoVibesVariant
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.policy.policy import PolicySpec
from mettagrid.policy.loader import initialize_or_load_policy
from mettagrid.simulator import Simulator

MODEL_PATH = sys.argv[1] if len(sys.argv) > 1 else "train_dir_5act/177889060032/model_000020.pt"
MAX_STEPS = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

competition_basic = None
for m in MISSIONS:
    if getattr(m, 'name', '') == 'basic':
        site = getattr(m, 'site', None)
        if site and getattr(site, 'name', '') == 'cogsguard_machina_1':
            competition_basic = m
            break

competition_basic.max_steps = MAX_STEPS
competition_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=8, wealth=1, initial_hearts=15),
}

no_vibes = NoVibesVariant()
competition_basic.variants = list(getattr(competition_basic, 'variants', []))
competition_basic.variants.append(no_vibes)

config = competition_basic.make_env()

policy = initialize_or_load_policy(
    PolicyEnvInterface.from_mg_cfg(config),
    PolicySpec(
        class_path="cogames.policy.tutorial_policy.TutorialPolicy",
        data_path=MODEL_PATH,
    ),
)

sim = Simulator(config)
sim.reset()

network = policy.network()
network.eval()

action_names = ["noop", "north", "south", "west", "east"]
action_counts = np.zeros((8, 5), dtype=int)
positions = [[] for _ in range(8)]

print(f"Running {MAX_STEPS} steps with model: {MODEL_PATH}")
print(f"Map size: {sim.map_width}x{sim.map_height}")
print()

for step in range(MAX_STEPS):
    obs = sim.get_observations()
    obs_tensor = torch.from_numpy(obs).unsqueeze(0) if len(obs.shape) == 2 else torch.from_numpy(obs)

    with torch.no_grad():
        if hasattr(network, 'forward'):
            actions_out, _, _, _ = network(obs_tensor)
        else:
            logits = network(obs_tensor)
            actions_out = torch.argmax(logits, dim=-1)

    if hasattr(actions_out, 'numpy'):
        actions = actions_out.numpy().flatten()
    else:
        actions = np.array(actions_out).flatten()

    for i in range(min(8, len(actions))):
        action_counts[i, actions[i]] += 1

    sim.step(actions)

    if step % 100 == 0 or step == MAX_STEPS - 1:
        stats = {}
        try:
            info = sim.get_episode_stats() if hasattr(sim, 'get_episode_stats') else {}
        except:
            info = {}
        print(f"Step {step}:")
        for i in range(8):
            pcts = action_counts[i] / max(1, action_counts[i].sum()) * 100
            print(f"  Agent {i}: " + " ".join(f"{name}={pcts[j]:.0f}%" for j, name in enumerate(action_names)))

print("\nFinal action distributions:")
for i in range(8):
    total = action_counts[i].sum()
    pcts = action_counts[i] / max(1, total) * 100
    print(f"  Agent {i} ({total} actions): " + " ".join(f"{name}={pcts[j]:.1f}%" for j, name in enumerate(action_names)))
