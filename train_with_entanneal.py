"""Training wrapper that implements entropy coefficient annealing.

Modifies the PufferRL trainer's config["ent_coef"] after each epoch,
annealing from ent_start to ent_end over anneal_epochs epochs.

Usage:
    python train_with_entanneal.py <mission_file> [model_path]

Env vars:
    COGAMES_ENT_START: Starting entropy coefficient (default: 0.1)
    COGAMES_ENT_END: Final entropy coefficient (default: 0.01)
    COGAMES_ENT_ANNEAL_EPOCHS: Epochs over which to anneal (default: 30)
    COGAMES_LR: Learning rate (default: 0.00092)
"""
import os
import sys
import importlib.util
import logging
from pathlib import Path

import pufferlib.pufferl as pufferl
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.policy.policy import PolicySpec
from mettagrid.policy.loader import initialize_or_load_policy

logger = logging.getLogger(__name__)

ENT_START = float(os.environ.get("COGAMES_ENT_START", "0.1"))
ENT_END = float(os.environ.get("COGAMES_ENT_END", "0.01"))
ANNEAL_EPOCHS = int(os.environ.get("COGAMES_ENT_ANNEAL_EPOCHS", "30"))
LR = float(os.environ.get("COGAMES_LR", "0.00092"))
TOTAL_STEPS = int(os.environ.get("COGAMES_STEPS", "100000000"))
CHECKPOINT_DIR = os.environ.get("COGAMES_CHECKPOINT_DIR", "./train_dir_entanneal")

mission_file = sys.argv[1] if len(sys.argv) > 1 else "train_arena_entanneal.py"
model_path = sys.argv[2] if len(sys.argv) > 2 else None

spec = importlib.util.spec_from_file_location("mission", mission_file)
mission_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mission_mod)
config = mission_mod.config

policy_class_path = "cogames.policy.tutorial_policy.TutorialPolicy"
policy = initialize_or_load_policy(
    PolicyEnvInterface.from_mg_cfg(config),
    PolicySpec(
        class_path=policy_class_path,
        data_path=model_path,
    ),
)
network = policy.network()

import torch
device = torch.device("cpu")
network.to(device)

use_rnn = True
bptt_horizon = 64

from cogames.train import _make_vecenv
vecenv = _make_vecenv(config, 256, device, policy_class_path)

total_agents = max(1, getattr(vecenv, "num_agents", 1))
auto_batch_size = total_agents * bptt_horizon

train_args = dict(
    env="cogames.cogs_vs_clips",
    device=device.type,
    total_timesteps=TOTAL_STEPS,
    minibatch_size=min(16384, auto_batch_size),
    batch_size="auto",
    data_dir=CHECKPOINT_DIR,
    checkpoint_interval=10,
    bptt_horizon=bptt_horizon,
    seed=1,
    use_rnn=use_rnn,
    torch_deterministic=True,
    cpu_offload=False,
    optimizer="adam",
    anneal_lr=True,
    precision="float32",
    learning_rate=LR,
    gamma=0.995,
    gae_lambda=0.90,
    update_epochs=1,
    clip_coef=0.2,
    vf_coef=2.0,
    vf_clip_coef=0.2,
    max_grad_norm=1.5,
    ent_coef=ENT_START,
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

print(f"Training with entropy annealing: {ENT_START} -> {ENT_END} over {ANNEAL_EPOCHS} epochs")
print(f"LR: {LR}, Total steps: {TOTAL_STEPS}")
if model_path:
    print(f"Fine-tuning from: {model_path}")

last_epoch = -1

while trainer.global_step < TOTAL_STEPS:
    eval_stats = trainer.evaluate()
    trainer_stats = trainer.train()

    current_epoch = trainer.epoch
    if current_epoch != last_epoch:
        last_epoch = current_epoch

        progress = min(current_epoch / ANNEAL_EPOCHS, 1.0)
        new_ent_coef = ENT_START + (ENT_END - ENT_START) * progress
        trainer.config["ent_coef"] = new_ent_coef

trainer.print_dashboard()
trainer.close()
print(f"\nTraining complete. Checkpoints saved to: {CHECKPOINT_DIR}")
