#!/bin/bash
# Run all Phase 2 experiments sequentially
# Key insight from Session 6: map_seed=42 is what makes training succeed
# Usage: bash scripts/run_experiments.sh

source /home/user/venv312/bin/activate

P1_BEST=$(ls -t train_dir_p1_anneal_m2x5_s42/stage1c/*/model_*.pt | head -1)
echo "Phase 1 best: $P1_BEST"

if [ -z "$P1_BEST" ]; then
    echo "ERROR: No Phase 1 checkpoint found! Run arena_anneal first."
    exit 1
fi

echo "=== Experiment 1: Phase 2 map42 seed=42 m2x5 (baseline reproduction) ==="
python scripts/train_curriculum_v2.py \
    --pipeline compmap --seed 42 --map-seed 42 --cogs 4 --parallel-envs 16 \
    --m2-factor 5 --weights "$P1_BEST"

echo ""
echo "=== Experiment 2: Phase 2 map42 seed=123 m2x5 (KEY: does map_seed=42 fix bad seed?) ==="
python scripts/train_curriculum_v2.py \
    --pipeline compmap --seed 123 --map-seed 42 --cogs 4 --parallel-envs 16 \
    --m2-factor 5 --weights "$P1_BEST"

echo ""
echo "=== Experiment 3: Phase 2 map42 seed=7 m2x5 (third seed for robustness) ==="
python scripts/train_curriculum_v2.py \
    --pipeline compmap --seed 7 --map-seed 42 --cogs 4 --parallel-envs 16 \
    --m2-factor 5 --weights "$P1_BEST"

echo ""
echo "=== Experiment 4: Phase 2 NO map_seed seed=123 m2x5 (control: no map fix) ==="
python scripts/train_curriculum_v2.py \
    --pipeline compmap --seed 123 --cogs 4 --parallel-envs 16 \
    --m2-factor 5 --weights "$P1_BEST"
