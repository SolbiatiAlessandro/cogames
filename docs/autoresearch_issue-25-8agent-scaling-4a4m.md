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

## 2026-03-31T00:05:00Z: starting to run baseline

**Command (machina_llm_roles, 4A4M scripted):**
```
source .env.openrouter.local && uv run cogames play -m cogsguard_machina_1 -c 8 \
  -p class=machina_llm_roles,kw.num_aligners=4,kw.llm_timeout_s=30,kw.scripted_miners=true \
  -s 1000 -r log --autostart
```
