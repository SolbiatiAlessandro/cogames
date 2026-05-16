"""Evaluate BC-trained model on competition environment.

Runs the BC model through full episodes and measures alignment performance.
Compares with scripted baseline.

Usage:
  python eval_bc.py [model_path] [num_episodes] [max_steps]
"""
import sys
import os
import numpy as np
import torch

sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), "src")))

from cogames.cogs_vs_clips.missions import MISSIONS
from cogames.cogs_vs_clips.cog import CogTeam
from cogames.cogs_vs_clips.variants import NoVibesVariant, NoClipsVariant
from mettagrid.simulator.simulator import Simulation
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from cogames.policy.tutorial_policy import TutorialPolicyNet

MODEL_PATH = sys.argv[1] if len(sys.argv) > 1 else "bc_models/bc_best.pt"
NUM_EPISODES = int(sys.argv[2]) if len(sys.argv) > 2 else 3
MAX_STEPS = int(sys.argv[3]) if len(sys.argv) > 3 else 3000
NUM_AGENTS = 8

# Action names for the 5-action space
ACTION_NAMES = ["noop", "move_north", "move_south", "move_west", "move_east"]

# Setup environment
competition_basic = None
for m in MISSIONS:
    if getattr(m, 'name', '') == 'basic':
        site = getattr(m, 'site', None)
        if site and getattr(site, 'name', '') == 'cogsguard_machina_1':
            competition_basic = m
            break

competition_basic.max_steps = MAX_STEPS
competition_basic.teams = {
    "cogs": CogTeam(name="cogs", num_agents=NUM_AGENTS, wealth=1, initial_hearts=200),
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

# Load BC model
print(f"Loading model from {MODEL_PATH}")
net = TutorialPolicyNet(env_interface)
state_dict = torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
net.load_state_dict(state_dict)
net.eval()
print(f"  Model loaded: {sum(p.numel() for p in net.parameters())/1e6:.1f}M params")

# Run evaluation
print(f"\n=== Evaluating BC model: {NUM_EPISODES} episodes, {MAX_STEPS} steps ===")

all_results = []
for ep in range(NUM_EPISODES):
    sim = Simulation(config, seed=100 + ep)
    agents = sim.agents()

    # LSTM states per agent
    lstm_states = {}
    for i in range(NUM_AGENTS):
        h = torch.zeros(1, 1, net.hidden_size)
        c = torch.zeros(1, 1, net.hidden_size)
        lstm_states[i] = (h, c)

    action_counts = {a: 0 for a in ACTION_NAMES}
    ep_aligned = 0

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

            obs_tensor = torch.from_numpy(obs_array).unsqueeze(0)  # [1, T, 3]
            h, c = lstm_states[i]
            state_dict_eval = {"lstm_h": h.squeeze(0), "lstm_c": c.squeeze(0)}

            with torch.no_grad():
                logits, _ = net(obs_tensor, state_dict_eval)

            lstm_states[i] = (
                state_dict_eval["lstm_h"].unsqueeze(0),
                state_dict_eval["lstm_c"].unsqueeze(0),
            )

            # Sample action (or argmax for deterministic eval)
            action_idx = int(logits.argmax(dim=-1).item())
            action_name = ACTION_NAMES[action_idx]
            action_counts[action_name] += 1

            from mettagrid.simulator import Action
            agent.set_action(Action(name=action_name))

        sim.step()

    stats = sim.episode_stats
    game = stats.get('game', {})
    aligned = game.get('cogs/aligned.junction.held', 0)
    hearts = game.get('cogs/heart.amount', 0)
    heart_withdrawn = game.get('cogs/heart.withdrawn', 0)

    all_results.append({
        'aligned': aligned,
        'hearts': hearts,
        'heart_withdrawn': heart_withdrawn,
        'actions': dict(action_counts),
    })

    total_actions = sum(action_counts.values())
    print(f"\n  Episode {ep+1}/{NUM_EPISODES}:")
    print(f"    aligned.junction.held = {aligned:.1f}")
    print(f"    hearts remaining = {hearts:.1f}, withdrawn = {heart_withdrawn:.1f}")
    print(f"    Action dist: " + ", ".join(f"{k}={v/total_actions*100:.1f}%" for k, v in action_counts.items()))
    sim.close()

# Summary
print(f"\n=== SUMMARY ===")
avg_aligned = np.mean([r['aligned'] for r in all_results])
avg_hearts = np.mean([r['hearts'] for r in all_results])
print(f"  Avg aligned.junction.held: {avg_aligned:.1f}")
print(f"  Avg hearts remaining: {avg_hearts:.1f}")
print(f"  Per-agent alignment: {avg_aligned / NUM_AGENTS:.2f}")
print(f"  Scripted baseline: 2573 aligned (321/agent)")
print(f"  Ratio vs scripted: {avg_aligned / 2573 * 100:.1f}%")
