# Autoresearch Issue 21: Intrinsic Motivation & Empowerment-Driven Exploration

Branch: `autoresearch/issue-21-intrinsic-motivation-exploration`

## Issue Summary

**Hypothesis:** Current exploration is random frontier-walking. By adding empowerment-like intrinsic motivation (maximize reachable states or information gain), agents would naturally discover junctions, avoid dead-ends, and build useful mental maps.

**Issue-specific success criteria:**
- Junctions discovered per 100 steps > 1.5 (vs current ~0.7)
- Map coverage (unique cells visited) > 50% of total free cells by step 500
- Agent reaches all 4 map corners (rows 6-7 and 91-92) by step 400
- Reward improvement at 1000 steps from better junction discovery

## 2026-03-29: autoresearch starting, my plan is...

My plan:
1. First understand the current state by running a baseline with the free LLM model (nemotron-nano-9b:free since nemotron-super-49b is out of paid credits)
2. Measure junction discovery rate, map coverage, and corner-reaching metrics
3. Implement Experiment A: Frontier novelty bonus (score frontiers by distance from all previously-visited cells, prefer unexplored quadrants)
4. Implement Experiment B: Information gain exploration (track unknown cells, explore toward largest contiguous unknown region)
5. Implement Experiment C: Empowerment proxy (BFS reachable-junction count to guide exploration)
6. Measure improvements in both the issue metrics AND mission reward

**Key context from previous research:**
- Best result: 1.24 reward (4A+0S, 2000 steps, cogsguard_machina_1.basic, seed=42)
- Main bottleneck: only 5 hearts from hub, agents aligned 6/7 junctions
- The scripted exploration code is in `aligner_agent.py` - `_frontier_cells`, `_alignment_frontier_cells`, `_explore_frontier`
- Current exploration is nearest-frontier BFS which is biased toward center
- Previous `_alignment_frontier_cells` tries to stay near hub/friendly junctions but misses far corners

**Key limitation:** nemotron-super-49b is out of credits. Can only use:
- `nvidia/nemotron-nano-9b-v2:free` - free but smaller model
- Previous research noted 8b models were catastrophic, but nano-9b may be different
- Will run baseline with free model first to establish current state

## 2026-03-29: starting to run baseline

Running: `cogames play -m cogsguard_machina_1.basic -c 4 -p class=machina_llm_roles,kw.llm_model=nvidia/nemotron-nano-9b-v2:free -s 2000 -r log --autostart`

---

## Experiment Log

