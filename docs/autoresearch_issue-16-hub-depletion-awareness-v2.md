# Autoresearch Issue-16: Hub Depletion Awareness (v2 - continuation)

Branch: `autoresearch/issue-16-hub-depletion-awareness-v2`

**Inherited from:** autoresearch/issue-16-hub-depletion-awareness (up to commit 97fcda3)

**Prior best:** 0.700 avg with gemma-3-12b (seeds 46-50) on 1000 steps 2A1M configuration
**Prior best (single run):** 0.770 on seed 46 with 12 hearts, 11 junctions
**Baseline (main):** 0.563 avg 3-aligner, 83 get_heart stale exits

**Issue metrics targets:**
- get_heart stale exits < 10 (achieved in all v3+ versions)
- reward > 0.92 (achieved at 2000 steps with v13; not consistently at 1000 steps)
- No agent stuck > 100 consecutive steps (achieved in all v3+ versions)

---

## 2026-03-30T: Autoresearch starting

My plan is to continue from where the previous researcher left off on issue-16. The prior work established:

1. Cross-role policy with hub depletion awareness (cooldown-based)
2. deposit_to_hub navigation fix (approach-cell BFS)
3. Element-aware mining via extractors_by_element
4. gemma-3-12b as the optimal model (~1s/decision vs 2s for nemotron-49b)

Key bottlenecks remaining after v16:
- True mean reward is ~0.57 (not 0.70 - the 0.700 was on lucky seeds 46-50)
- LLM timing variance drives most of the reward variance
- make_heart cycle depends on element diversity in deposits
- At 1000 steps, only ~2-3 make_heart cycles can complete

My experiments will focus on:
1. **Experiment A**: Verify current gemma-3-12b performance on seeds 42-44 (establish true baseline)
2. **Experiment B**: Reduce LLM call latency further - try faster models or prompt compression
3. **Experiment C**: Improve miner element diversity with hardcoded element cycling (not LLM-guided)
4. **Experiment D**: Try the v19 idea of element cycling with small return_load (10-15 resources)
5. **Experiment E**: Improve aligner exploration to find more junctions faster
6. **Experiment F**: Try deposit routing improvements - maybe skip hub and go directly to extractor cycling

---

## 2026-03-30T: Starting to run baseline

Running baseline to get current state of the code.

Configuration: 2A1M (2 aligners + 1 miner), seeds 42-44, 1000 steps, gemma-3-12b

---
