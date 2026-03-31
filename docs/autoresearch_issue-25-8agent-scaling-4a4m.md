# Autoresearch Issue 25: 8-Agent Scaling with Scripted Miners (4A4M)

Branch: `autoresearch/issue-25-8agent-scaling-4a4m`

**Issue direction:**
- Use 4 LLM aligners + 4 scripted miners (no LLM for miners) to achieve high total reward at 8 agents
- Success: mission_reward total > 4.0 at 1000 steps (0.50/agent avg)
- Stretch: > 6.0 total (0.75/agent)

**Key background:**
- PR #18 merged: hub depletion awareness + make_heart cycle active
- 3A cross_role post-merge: 0.7055/agent (+37%)
- 4A4M scripted pre-merge: 0.4195/agent (3.356 total) — best 8-agent result so far
- 4A4M LLM post-merge: 0.4043/agent (3.234 total)
- Critical: scripted miners outperform LLM miners at scale

**Issue suggests:**
1. Baseline 4A4M scripted at 1000 steps
2. fast-extractor-abandon (threshold 20→3)
3. proximity junction claiming
4. aligner sweep: 3A5M, 4A4M, 5A3M, 6A2M
5. gemma-3-12b for faster LLM
6. LLM timeout error handling

---

## 2026-03-31T00:00:00Z: autoresearch starting, my plan is to...

**Plan:**
1. Run baseline: 4A4M scripted miners at 1000 steps with cross_role aligners (post-merge)
2. Apply fast-extractor-abandon (threshold 20→3) from issue #24
3. Sweep aligner counts: 3A5M, 4A4M, 5A3M, 6A2M with scripted miners
4. Test gemma-3-12b model
5. Add proximity junction claiming if above yields improvement

**Hypothesis:**
The biggest wins will come from:
1. Optimal aligner/miner split — more aligners means more junction alignment, more miners means more hearts
2. Fast extractor abandon (issue #24 showed this improved 2A1M performance)
3. Using the cross_role policy (with hub depletion awareness) instead of machina_llm_roles policy for aligners

**Current state:** Post-merge, 3A cross_role is at 0.7055/agent but 8A with 4A4M LLM is only 0.4043/agent.
The director says the highest-leverage experiment is combining cross_role aligners (hub depletion awareness) with scripted miners.

The `machina_llm_roles` policy already has `scripted_miners=true` parameter.
The `cross_role` policy does NOT have a `scripted_miners` flag.

Two approaches:
- Option A: Use machina_llm_roles with scripted_miners=true and 4 aligners
- Option B: Add scripted_miners to cross_role policy

I'll start with Option A (machina_llm_roles, scripted_miners=true) since it exists already and test if we can match the cross_role improvement, then consider Option B.

---

## 2026-03-31T12:00:00Z: session 2 starting, reset cross_role experiments, new direction

**Previous session summary:**
- Baseline: machina_llm_roles 4A4M scripted = 0.495/agent avg (seeds 42-47)
- Cross_role scripted experiments v1-v8 ALL failed to beat machina baseline
- Root cause: cross_role aligners fail catastrophically on seeds 46/47 (explore_near_hub doesn't find aligner station)
- machina_llm_roles uses AlignerPolicyImpl._gear_up which has expected station position nav - works on all seeds
- Attempted fixes (expected station nav, delayed nav, 2x stale threshold) all created contamination problems on other seeds
- Decision: reset all cross_role experiments (git reset --hard 9da719f), discard cross_role path

**New direction:**
- machina_llm_roles is stable, works on all seeds
- Try aligner count sweeps: 5A3M, 6A2M, 3A5M, 2A6M to find optimal split
- Try lower return_load for miners (20→10) to make miners deposit more frequently
- Consider adding hub depletion awareness to machina LLMAlignerPolicyImpl

**Hypothesis:**
- More aligners (5A3M, 6A2M) should improve junction score since aligners score points
- Lower return_load (10-20) means miners return to hub more frequently, depositing minerals faster
- These two together might push above 0.5/agent avg target

## 2026-03-31T12:30:00Z: experiment loop 1 - aligner count sweep

**Hypothesis:** More aligners should improve junction score since aligners score points.
**Experiments:** 3A5M, 4A4M (baseline), 5A3M, 6A2M - all with machina_llm_roles, fast-fail LLM

**Results:**
| Config | seed42 | seed43 | seed44 | seed45 | seed46 | seed47 | AVG |
|---|---|---|---|---|---|---|---|
| 6A2M | 0.453 | 0.591 | 0.430 | 0.294 | 0.607 | 0.429 | 0.467 |
| 4A4M (baseline) | 0.521 | 0.366 | 0.358 | 0.639 | 0.487 | 0.596 | 0.495 |
| 3A5M | 0.450 | 0.484 | 0.368 | 0.520 | 0.518 | 0.362 | 0.450 |
| **5A3M** | **0.564** | **0.543** | **0.337** | **0.614** | **0.565** | **0.614** | **0.540** |

**Finding:** 5A3M is the optimal split! +9% over baseline.
- 5A3M wins 4 out of 6 seeds over baseline
- seed 44 is the weak point (0.337 vs 0.358 baseline)
- 6A2M is worse because 2 miners aren't enough to keep up element deposits
- 3A5M is worse because fewer aligners means fewer junctions claimed
- Next: try 5A3M with return_load=20 to see if faster miner cycling helps

---

## 2026-03-31T00:05:00Z: starting to run baseline

**Command (machina_llm_roles, 4A4M scripted):**
```
source .env.openrouter.local && uv run cogames play -m cogsguard_machina_1 -c 8 \
  -p class=machina_llm_roles,kw.num_aligners=4,kw.llm_timeout_s=30,kw.scripted_miners=true \
  -s 1000 -r log --autostart
```
