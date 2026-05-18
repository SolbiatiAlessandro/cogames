#!/bin/bash
# Evaluate Phase 2 checkpoints at multiple step lengths
# Usage: bash scripts/eval_phase2.sh <train_dir>
# Example: bash scripts/eval_phase2.sh train_dir_p2_longep_m2x5_s42_ms42

source /home/user/venv312/bin/activate

DIR="${1:?Usage: $0 <train_dir>}"

if [ ! -d "$DIR" ]; then
    echo "ERROR: Directory $DIR not found"
    exit 1
fi

CHECKPOINTS=$(ls -t "$DIR"/*/model_*.pt 2>/dev/null)
if [ -z "$CHECKPOINTS" ]; then
    echo "ERROR: No checkpoints found in $DIR"
    exit 1
fi

echo "Evaluating checkpoints in $DIR"
echo ""

# Quick eval at 500 steps (fast, 3 episodes)
echo "=== Quick eval @500 steps ==="
python scripts/batch_eval.py $DIR/*/model_*.pt \
    --steps 500 --episodes 3 --cogs 8 --temperature 0.7

echo ""
echo "=== Full eval @10000 steps (competition length) ==="
# Pick best 3 checkpoints from 500-step eval and evaluate at 10K
# For now, evaluate all at 10K (slower but complete)
python scripts/batch_eval.py $DIR/*/model_*.pt \
    --steps 10000 --episodes 3 --cogs 8 --temperature 0.7
