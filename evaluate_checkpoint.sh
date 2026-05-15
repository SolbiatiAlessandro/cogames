#!/bin/bash
# Evaluate a trained RL checkpoint on the competition mission
# Usage: ./evaluate_checkpoint.sh <checkpoint_dir_or_pt_file> [episodes] [steps]

set -e

CHECKPOINT="$1"
EPISODES="${2:-5}"
STEPS="${3:-3000}"

if [ -z "$CHECKPOINT" ]; then
    echo "Usage: $0 <checkpoint_dir_or_pt_file> [episodes=5] [steps=3000]"
    echo ""
    echo "Examples:"
    echo "  $0 ./train_dir_cli/<run_id>"
    echo "  $0 ./train_dir_cli/<run_id>/model_000050.pt"
    exit 1
fi

# If it's a directory, use it as a bundle
if [ -d "$CHECKPOINT" ]; then
    POLICY_ARG="$CHECKPOINT"
else
    # It's a .pt file, use class=tutorial,data=<path>
    POLICY_ARG="class=tutorial,data=$CHECKPOINT"
fi

echo "=== Evaluating RL checkpoint ==="
echo "Policy: $POLICY_ARG"
echo "Mission: cogsguard_machina_1.basic"
echo "Episodes: $EPISODES, Steps: $STEPS"
echo ""

source .venv/bin/activate

# Run evaluation on competition mission
python -m cogames run \
    -m cogsguard_machina_1.basic \
    -p "$POLICY_ARG" \
    -e "$EPISODES" \
    -s "$STEPS" \
    --seed 42 \
    --format yaml 2>&1

echo ""
echo "=== Evaluation complete ==="
