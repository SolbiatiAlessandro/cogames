# Experiment Log: claude-amazing-meitner-eTn0X

## Issue: #61 — Agent longevity: survive 8000+ steps in 10k-step online matches

**2026-05-03T08:00: autoresearch starting, my plan is to...**

Work on issue #61 — agent longevity. Our agents die at 3000-5500 steps in 10k-step online matches, losing 45-65% of the game. The offline eval runs 3000 steps which hides this problem entirely.

### Key findings from code review:
1. **Aligner `_read_hp()` returns `None`** (aligner_agent.py:561) — HP retreat is completely disabled for aligners. The comment says "causes rapid oscillation near territory boundaries" but this means aligners have zero HP management.
2. **Miner HP retreat threshold is 25%** (llm_skills.py:846) — very aggressive, only retreats when nearly dead.
3. **Hub heart depletion**: SharedMap tracks `hub_hearts_withdrawn` but agents don't budget hearts for the full 10k game.

### Plan:
1. Run 3000-step baseline (standard)
2. Run 10000-step baseline to observe death patterns
3. Enable HP retreat for aligners with a better implementation that avoids oscillation
4. Tune miner HP retreat threshold higher
5. Add heart conservation logic

**2026-05-03T08:01: starting to run baseline**

### Baseline results (3000 steps, 8-agent self-play):
- Seed 42: total=1126.10, avg=140.76, 0 deaths
- 10k self-play: total=4149.59, no deaths (all agents at 100 HP — no enemies in self-play)
- 10k CvC (4 ours + 4 starter): same — no deaths because both teams are cogs

Key finding: **hp_regen=-1** means agents lose 1 HP/tick naturally. Hub territory heals agents (+100 HP/tick). In self-play, all agents are always in friendly territory → never die. Online deaths come from leaving friendly territory (enemy clips territory has no healing).

### Experiment 1: Enable HP retreat for aligners (commit 2016949)

Changes:
- aligner_agent.py: `_read_hp()` now returns actual HP (was returning None)
- machina_llm_roles_policy.py: Hysteresis thresholds — retreat at 50% HP, resume at 85% (was 70%/70% = oscillation)
- Retreat prioritizes hub (which heals) over friendly junctions
- llm_skills.py: Miner HP retreat raised from 25% → 40%

5-seed 3k results: avg=1152.19, no regression (baseline was ~1141)
HP retreat confirmed firing: "agent=5 HP_LOW hp=49/100 (49%) retreating to hub"

Uploaded as lessandro-ohm-bekkenze-maha-bekkenze:v8 to beta-cvc.

**2026-05-03T09:10: starting new experiment loop**
Want to try: late-game defensive mode + heart conservation for 10k survival.
