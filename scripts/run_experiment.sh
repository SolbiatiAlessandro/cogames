#!/bin/bash
# Run an experiment and extract key metrics
set -e
source /home/user/cogames/.venv/bin/activate
export OPENROUTER_API_KEY=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

STEPS=${1:-3000}
SEED=${2:-42}
ALIGNERS=${3:-5}
DESC=${4:-"experiment"}

echo "=== Running: $DESC (steps=$STEPS, seed=$SEED, ${ALIGNERS}A${$((8-ALIGNERS))}M) ==="

OUTPUT=$(cogames play -m cogsguard_machina_1 -c 8 -p "class=cross_role,kw.num_aligners=$ALIGNERS" -s "$STEPS" -r log --seed "$SEED" --autostart 2>&1)

# Extract key metrics
SCORE=$(echo "$OUTPUT" | grep "Score.*per cog" | grep -oP '[\d.]+' | tail -1)
JUNCTIONS=$(echo "$OUTPUT" | grep -oP "cogs/aligned\.junction\.gained': [\d.]+" | grep -oP '[\d.]+' || echo "0")
JUNCTION_HELD=$(echo "$OUTPUT" | grep -oP "cogs/aligned\.junction\.held': [\d.]+" | grep -oP '[\d.]+' || echo "0")
C_DEP=$(echo "$OUTPUT" | grep -oP "cogs/carbon\.deposited': [\d.]+" | grep -oP '[\d.]+' || echo "0")
GE_DEP=$(echo "$OUTPUT" | grep -oP "cogs/germanium\.deposited': [\d.]+" | grep -oP '[\d.]+' || echo "0")
SI_DEP=$(echo "$OUTPUT" | grep -oP "cogs/silicon\.deposited': [\d.]+" | grep -oP '[\d.]+' || echo "0")
OX_DEP=$(echo "$OUTPUT" | grep -oP "cogs/oxygen\.deposited': [\d.]+" | grep -oP '[\d.]+' || echo "0")
HEARTS=$(echo "$OUTPUT" | grep -oP "cogs/heart\.withdrawn': [\d.]+" | grep -oP '[\d.]+' || echo "0")
DEATHS=$(echo "$OUTPUT" | grep -oP "'death': [\d.]+" | grep -oP '[\d.]+' | paste -sd+ | bc || echo "0")

TOTAL_DEP=$((${C_DEP%.*} + ${GE_DEP%.*} + ${SI_DEP%.*} + ${OX_DEP%.*}))

echo "Score/cog: $SCORE"
echo "Junctions gained: $JUNCTIONS"
echo "Junction held: $JUNCTION_HELD"
echo "Hearts withdrawn: $HEARTS"
echo "Total deposits: $TOTAL_DEP (C=$C_DEP Ge=$GE_DEP Si=$SI_DEP Ox=$OX_DEP)"
echo "Deaths: $DEATHS"
echo "=== Done ==="
