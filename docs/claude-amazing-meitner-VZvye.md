# Experiment Log: claude/amazing-meitner-VZvye

Issue: #62 — Junction capture rate & exploration coverage

## 2026-05-07T00:00: Autoresearch starting

**Plan:** Follow director's recommended experiment order from Session 28:
1. JUNCTION_ALIGN_DISTANCE 20→15 (one-line change, validated in C4lUC branch at +5%)
2. explore_beyond_aligned — discover junctions beyond aligned network
3. Quadrant assignment — spatial dispersion for agents

**Current state:** Main branch has v52 policy code (reverted from v59). `_JUNCTION_ALIGN_DISTANCE=20` in aligner_agent.py but config.py already has 15 — the policy ignores config.py.

## 2026-05-07T00:01: Starting baseline run

Running baseline with current code on seeds 42, 1, 7 (8 agents, 5000 steps).

## 2026-05-07T05:22: Baseline results

| Seed | total_reward | junction.held | heart.gained |
|------|-------------|---------------|--------------|
| 42 | 1875.99 | 0 | 63 |
| 1 | 2101.24 | 0 | 71 |
| 7 | 2140.73 | 0 | 68 |
| **Avg** | **2039.32** | **0** | **67.3** |

## 2026-05-07T05:32: Experiment 1 — JUNCTION_ALIGN_DISTANCE 20→15

**Hypothesis:** Reducing junction align distance from 20 to 15 forces aligners to stay closer to aligned network, creating denser territory. C4lUC branch reported +5% with this change.

**Result: REGRESSION (-3.5%)**

| Seed | Baseline | Exp1 | Delta |
|------|----------|------|-------|
| 42 | 1875.99 | 1807.69 | -3.6% |
| 1 | 2101.24 | 1966.87 | -6.4% |
| 7 | 2140.73 | 2129.69 | -0.5% |
| **Avg** | **2039.32** | **1968.08** | **-3.5%** |

**Analysis:** C4lUC's +5% was measured on the worse hCVEi codebase. On v52 (which already has better navigation), reducing the search radius just causes aligners to miss junctions. Reverted.

**Decision: DISCARD**

## 2026-05-07T05:50: Starting Experiment 2 — explore_beyond_aligned

**Hypothesis:** When an aligner has a heart but no known unaligned junctions within range, instead of generic exploration, explore AWAY from the aligned network to discover new junctions. Currently aligners explore near hubs/friendly junctions, which re-traverses already-explored territory.

**Result: NEUTRAL (+0.6%)**

| Seed | Baseline | Exp2 | Delta |
|------|----------|------|-------|
| 42 | 1875.99 | 1875.99 | 0.0% |
| 1 | 2101.24 | 2140.56 | +1.9% |
| 7 | 2140.73 | 2137.24 | -0.2% |
| **Avg** | **2039.32** | **2051.26** | **+0.6%** |

**Analysis:** The code path rarely triggers in self-play because 8 agents explore quickly and find junctions before the "beyond" exploration is needed. junction.aligned_by_agent=52 is identical to baseline. No regression, keeping the code.

**Decision: KEEP (no regression, good insurance for sparse maps)**

## 2026-05-07T06:30: Starting Experiment 3 — Quadrant-based exploration dispersion

**Hypothesis:** Assigning each aligner a preferred quadrant (NW/NE/SW/SE relative to hub) will spread exploration coverage. Currently all aligners pick the nearest frontier cell, causing them to cluster. With quadrant bias, each aligner gravitates toward a different map section, discovering more junctions faster.

**Result: REGRESSION (-5.2%).** Fixed quadrants force agents away from optimal paths.

Also tried peer-dispersion variant (avoid cells near other agents): -1.4%. Both DISCARDED.

## 2026-05-07T07:20: Experiment 4 — Per-agent move_blocked_cells

**Hypothesis:** `move_blocked_cells` is shared via SharedMap. When agent A collides with agent B, ALL agents permanently treat that cell as blocked. This causes stale blocks to accumulate and restrict BFS. Fix: un-share move_blocked_cells (keep per-agent) and use only temporary cooldowns.

**Result: NEUTRAL (~0%)**. No regression, cleaner architecture. Kept.

## 2026-05-07T07:55: Experiment 5 — Remove hub_dist bias from junction targeting

**Hypothesis:** The cascade scoring adds `+ hub_dist * 0.2` penalty, which could make aligners skip closer junctions. Removing it = always go to nearest.

**Result: REGRESSION (-3.8%).** The hub_dist bias HELPS by building alignment network outward from hub — removing it breaks the cascade effect. Reverted.

## 2026-05-07T08:05: Experiment 6 — Faster junction blacklisting

**Hypothesis:** When align_neutral exits as "stuck" (20 steps), the agent retries the same junction 4-5 times before the 100-step timeout triggers blacklisting. Fix: blacklist on FIRST stuck/stale exit.

**Result: KEEP (neutral, no regression)**

Combined results (explore_beyond + per-agent blocks + faster blacklist):

| Seed | Baseline | Combined | Delta | Junctions (B→E) |
|------|----------|----------|-------|------------------|
| 42 | 1875.99 | 1875.99 | 0.0% | 52→52 |
| 1 | 2101.24 | 2140.56 | +1.9% | 58→59 |
| 7 | 2140.73 | 2147.22 | +0.3% | ~60→60 |
| 5 | — | 1837.86 | — | —→51 |
| 13 | — | 2059.50 | — | —→57 |

**Analysis:** Junction count is near-identical to baseline. Self-play total_reward is dominated by mining reward, not junction alignment. junction.held=0 in all self-play runs. junction.aligned_by_agent≈52 regardless of policy changes. v52 policy is already near-optimal for self-play. Real improvements must target junction alignment SPEED (faster = more held time online).

**Decision: KEEP all three changes (no regression, cleaner architecture, insurance for sparse maps)**

## 2026-05-07T08:45: Strategic pivot — targeting alignment SPEED

Self-play experiments show junction COUNT is saturated (~52 for seed 42). Online score = junction.held/10000, which rewards EARLIER alignment. Focus shifts to reducing time-to-first-alignment and time-to-all-aligned.

Key bottlenecks identified:
1. **gear_up duration** — miners/aligners spend early steps mining for hearts before aligning
2. **exploration inefficiency** — agents re-traverse known territory
3. **stuck/stale exits** — wasted steps when navigation fails
4. **cascade ordering** — suboptimal junction sequence slows network expansion
