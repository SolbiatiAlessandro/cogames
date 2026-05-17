#!/bin/bash
# Evaluate multiple RL checkpoints at different step counts
# Usage: bash scripts/eval_sweep.sh <train_dir> [epochs] [step_counts]
# Example: bash scripts/eval_sweep.sh train_dir_curriculum_p1_arena_tc/177904134931 "40 60 80" "500 1000"

set -e
source /home/user/cogames/.venv/bin/activate

TRAIN_DIR="${1:?Usage: eval_sweep.sh <train_dir> [epochs] [step_counts]}"
EPOCHS="${2:-60 70 80 90 100}"
STEP_COUNTS="${3:-500 1000}"
EPISODES=5
COGS=4
MISSION="cogsguard_machina_1.basic"

echo "epoch	steps	avg_reward	peak_reward	all_rewards"

for epoch in $EPOCHS; do
    ckpt="${TRAIN_DIR}/model_$(printf '%06d' $epoch).pt"
    if [ ! -f "$ckpt" ]; then
        echo "# Checkpoint not found: $ckpt"
        continue
    fi

    for steps in $STEP_COUNTS; do
        result=$(python scripts/eval_rl.py \
            --checkpoint "$ckpt" \
            --steps "$steps" \
            --episodes "$EPISODES" \
            --cogs "$COGS" \
            --mission "$MISSION" \
            --seed 100 \
            2>&1)

        avg=$(echo "$result" | grep "Average per-agent" | sed 's/.*: //')
        peak=$(echo "$result" | grep "Peak per-agent" | sed 's/.*: //')
        all=$(echo "$result" | grep "All rewards" | sed 's/.*: //')

        echo "${epoch}	${steps}	${avg}	${peak}	${all}"
    done
done
