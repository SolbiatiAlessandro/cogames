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
