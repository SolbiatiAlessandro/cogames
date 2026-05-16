"""Evaluate a checkpoint on competition map with detailed stats."""
import sys
import os
import torch
import numpy as np

os.environ.setdefault("COGAMES_ENT_COEF", "0.005")

def eval_checkpoint(model_path, config_module, num_episodes=3, max_steps=5000):
    from cogames.cogs_vs_clips.missions import MISSIONS
    from cogames.cogs_vs_clips.cog import CogTeam
    from cogames.cogs_vs_clips.variants import NoVibesVariant, NoClipsVariant
    from cogames.cogs_vs_clips.reward_variants import apply_reward_variants
    from cogames.policy.tutorial_policy import TutorialPolicyNet, load_policy_data

    from mettagrid.config.game_value import stat
    from mettagrid.config.reward_config import reward
    import importlib.util

    spec = importlib.util.spec_from_file_location("config_mod", config_module)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    config = mod.config

    from mettagrid.mettagrid_env import MettagridEnv

    env = MettagridEnv(config)
    obs, info = env.reset()
    pei = env.policy_env_interface

    policy = TutorialPolicyNet(pei, hidden_size=512)
    policy_data = load_policy_data(model_path)
    policy.load_state_dict(policy_data)
    policy.eval()

    num_agents = pei.num_agents
    print(f"Evaluating {model_path}")
    print(f"  Agents: {num_agents}, Max steps: {max_steps}")
    print(f"  Config: {config_module}")
    print()

    total_rewards = np.zeros(num_agents)
    episode_stats = []

    for ep in range(num_episodes):
        obs, info = env.reset()
        hidden = None
        ep_reward = np.zeros(num_agents)
        move_success = 0
        move_fail = 0

        for step in range(max_steps):
            obs_tensor = torch.FloatTensor(obs).unsqueeze(0)
            with torch.no_grad():
                actions, _, _, hidden = policy(obs_tensor, hidden)
            actions_np = actions.squeeze(0).numpy()

            obs, rewards, dones, truncated, info = env.step(actions_np)
            ep_reward += rewards

            if step % 500 == 0 and step > 0:
                stats = env.get_episode_stats() if hasattr(env, 'get_episode_stats') else {}
                print(f"  Step {step}: reward_so_far={ep_reward.mean():.3f}")

        game_stats = {}
        try:
            stats = env.get_stats() if hasattr(env, 'get_stats') else {}
            game_stats = stats
        except:
            pass

        episode_stats.append({
            'reward': ep_reward.mean(),
            'stats': game_stats,
        })
        total_rewards += ep_reward
        print(f"  Episode {ep+1}/{num_episodes}: mean_reward={ep_reward.mean():.3f}, per_agent={ep_reward}")

    avg_reward = total_rewards / num_episodes
    print(f"\nAverage reward per agent: {avg_reward.mean():.3f}")
    print(f"Per-agent rewards: {avg_reward}")

    env.close()
    return avg_reward.mean()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python eval_checkpoint.py <model_path> [config_module] [num_episodes]")
        sys.exit(1)

    model_path = sys.argv[1]
    config_module = sys.argv[2] if len(sys.argv) > 2 else "train_competition_long.py"
    num_episodes = int(sys.argv[3]) if len(sys.argv) > 3 else 3

    eval_checkpoint(model_path, config_module, num_episodes)
