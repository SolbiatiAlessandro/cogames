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

### Baseline comparison (release engine, cogames 0.25.6):

| Metric | Baseline | Improved | Delta |
|--------|----------|----------|-------|
| Reward (5-seed avg) | 74.35 | 71.57 | -3.7% |
| Deaths (5-seed avg) | 32.0 | 16.0 | -50.0% |
| Aligned (5-seed avg) | 83.4 | 78.2 | -5.2 |

Decision: **KEEP** — deaths halved is the primary goal of issue #61. Reward penalty is small and expected (time spent retreating). In 10k online matches, surviving longer should produce more total reward.

**2026-05-03T09:10: starting new experiment loop**
Goal: reduce the retreat penalty — make agents more productive while surviving.

### Online analysis (v8, HP retreat 50%/85%):
- Leaderboard: #88, score=31.53 (v1 was #39, score=35.00) — WORSE
- Best match (49.28): 104 junctions aligned, 1281 carbon deposited, 11.25 avg deaths
- Worst match (0.80): 6 junctions aligned, 40 carbon deposited, 0.5 avg deaths, 41.5% move failures
- Key insight: low scores correlate with low exploration (199 unique cells) and stuck agents, NOT with deaths
- The HP retreat penalty is real in online 10k matches — agents spend too much time retreating

### Experiment 2: Tighten HP hysteresis (commit 31252b0)

Changes:
- Aligner HP retreat: 50%/85% → 40%/70% (retreat later, resume sooner)
- Miner HP retreat exit: 85% → 70% (resume mining sooner)

| Metric | Baseline | Exp1 (50/85) | Exp2 (40/70) |
|--------|----------|-------------|-------------|
| Reward | 74.35 | 71.57 (-3.7%) | 74.52 (+0.2%) |
| Deaths | 32.0 | 16.0 (-50%) | 20.6 (-35%) |
| Aligned | 83.4 | 78.2 (-5.2) | 81.2 (-2.2) |

Decision: **ADVANCE** — reward matches baseline while still cutting deaths 35%. Best tradeoff found.

### Experiment 3: Productive defend mode (commit f246cea)
When hearts depleted and agent enters defend mode, explore alignment frontier instead of sitting idle.
No-op in 3k eval (defend never triggers). Online-only improvement.

### Parameter scan: aligner ratio
| Aligners | Reward (3-seed avg) |
|----------|-------------------|
| 3 | 72.01 |
| 4 (default) | 72.73 |
| 5 | 80.99 → 74.85 (5-seed: seed 45 crashes) |
| 6 | 57.46 |

5 aligners helps on 3 seeds but high variance with seed 45. Staying with 4 (default).

### Parameter scan: stuck_threshold
| Value | Reward (3-seed avg) |
|-------|-------------------|
| 10 | 60.11 |
| 15 | 64.68 |
| 20 (default) | 72.73 |
| 30 | 77.25 → 79.20 (5-seed) |

### Experiment 6: stuck_threshold=30 (commit b643798)
Raising stuck_threshold from 20 to 30 gives agents more patience before declaring navigation deadlocks. Fewer premature unstuck/explore cycles.

| Metric | Baseline | Exp2 (HP 40/70) | Exp6 (HP + ST=30) |
|--------|----------|-----------------|-------------------|
| Reward | 74.35 | 74.52 (+0.2%) | 79.20 (+6.5%) |
| Deaths | 32.0 | 20.6 (-35%) | 19.0 (-41%) |
| Aligned | 83.4 | 81.2 (-2.6%) | 86.2 (+3.4%) |

Decision: **ADVANCE** — best result yet. +6.5% reward, -41% deaths, +3% aligned vs baseline.
Uploaded as v11 to beta-cvc.
