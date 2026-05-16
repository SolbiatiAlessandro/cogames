"""Behavioral cloning: pre-train TutorialPolicyNet from scripted policy demos.

Trains the RL policy's neural network to imitate the scripted policy's actions.
This gives the RL policy a starting point with basic navigation and alignment
behavior, which can then be fine-tuned with RL.

Usage:
    source .venv/bin/activate
    # 1. Collect demos
    python scripts/collect_demonstrations.py --episodes 20 --output demos_arena.pt
    # 2. Run behavioral cloning
    python scripts/behavioral_cloning.py --demos demos_arena.pt --epochs 100 --output bc_weights.pt
    # 3. Fine-tune with RL
    python scripts/train_rl_fixed_map.py --policy "class=tutorial,data=bc_weights.pt" ...
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from cogames.cli.mission import get_mission
from cogames.policy.tutorial_policy import TutorialPolicyNet
from mettagrid.policy.policy_env_interface import PolicyEnvInterface


def main():
    parser = argparse.ArgumentParser(description="Behavioral cloning from demonstrations")
    parser.add_argument("--demos", required=True, help="Path to demonstration data (.pt)")
    parser.add_argument("--output", default="bc_weights.pt", help="Output weights file")
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=256, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--mission", default="cogsguard_arena.basic", help="Mission (for policy init)")
    parser.add_argument("--cogs", type=int, default=8, help="Number of agents")
    args = parser.parse_args()

    demo_data = torch.load(args.demos, weights_only=False)
    obs = demo_data["observations"]
    actions = demo_data["actions"]

    print(f"Loaded demos: obs={obs.shape}, actions={actions.shape}")
    print(f"Action names: {demo_data['action_names']}")
    print(f"Total timesteps: {demo_data['total_steps']}, episodes: {demo_data['episodes']}")

    num_timesteps, num_agents, num_tokens, token_dim = obs.shape
    obs_flat = obs.reshape(-1, num_tokens, token_dim).float()
    actions_flat = actions.reshape(-1)

    print(f"Flattened: obs={obs_flat.shape}, actions={actions_flat.shape}")

    action_counts = torch.bincount(actions_flat, minlength=len(demo_data["action_names"]))
    total = actions_flat.shape[0]
    for i, name in enumerate(demo_data["action_names"]):
        print(f"  {name}: {action_counts[i].item()} ({100*action_counts[i].item()/total:.1f}%)")

    _, env_cfg, _ = get_mission(args.mission, cogs=args.cogs)
    policy_env_info = PolicyEnvInterface.from_mg_cfg(env_cfg)

    net = TutorialPolicyNet(policy_env_info)
    print(f"\nModel params: {sum(p.numel() for p in net.parameters()):,}")

    dataset = TensorDataset(obs_flat, actions_flat)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True, drop_last=True)

    optimizer = optim.Adam(net.parameters(), lr=args.lr)
    criterion = nn.CrossEntropyLoss()

    best_loss = float("inf")
    best_acc = 0.0

    for epoch in range(args.epochs):
        net.train()
        total_loss = 0.0
        total_correct = 0
        total_samples = 0

        for batch_obs, batch_actions in loader:
            logits, _ = net(batch_obs)
            loss = criterion(logits, batch_actions)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * batch_obs.shape[0]
            preds = logits.argmax(dim=-1)
            total_correct += (preds == batch_actions).sum().item()
            total_samples += batch_obs.shape[0]

        avg_loss = total_loss / total_samples
        accuracy = total_correct / total_samples

        if avg_loss < best_loss:
            best_loss = avg_loss
            best_acc = accuracy
            torch.save(net.state_dict(), args.output)

        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"Epoch {epoch+1}/{args.epochs}: loss={avg_loss:.4f}, acc={accuracy:.4f} (best loss={best_loss:.4f}, acc={best_acc:.4f})")

    print(f"\nBest: loss={best_loss:.4f}, accuracy={best_acc:.4f}")
    print(f"Saved weights to {args.output}")
    print(f"\nTo fine-tune with RL:")
    print(f"  python scripts/train_rl_fixed_map.py --policy 'class=tutorial,data={args.output}' ...")


if __name__ == "__main__":
    main()
