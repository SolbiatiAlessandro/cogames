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
