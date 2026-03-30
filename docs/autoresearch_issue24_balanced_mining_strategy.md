# Autoresearch Issue 24: Balanced Mining Strategy for make_heart Cycle Optimization

Branch: `autoresearch/issue-24-balanced-mining-strategy`
Issue: https://github.com/SolbiatiAlessandro/cogames/issues/24

**Setup:** `cogsguard_machina_1.basic`, seed=42, cloud LLM (nvidia/llama-3.3-nemotron-super-49b-v1.5 via OpenRouter)

---

## 2026-03-29T: autoresearch starting, my plan is to...

Implement balanced mining strategy as described in issue #24. The issue identifies that:
- make_heart requires 7 of EACH of 4 elements (28 total)
- Current miners deposit heavily skewed resources (e.g., 30 oxygen but only 1 germanium)
- Fixing balance could create 1 heart per 28 resources vs current 100+ resources for same outcome

My plan:
1. Run baseline to understand current state (OpenRouter API budget may be limited)
2. Implement element-aware mining: track extractor types by element, prefer rarest-needed element
3. Implement round-robin extraction: ensure balanced coverage of all 4 element types
4. Test with 2A1M configuration (2 aligners + 1 miner) per issue suggestion

IMPORTANT NOTE: The OpenRouter API key returns 402 Payment Required. This means I need to use the scripted fallback approach (no LLM) or use the machina_roles scripted policy. The key finding from autoresearch_22_march is that scripted miners + LLM aligners is the best approach (2.260 reward with 3 aligners at 1000 steps). Without LLM, scripted machina_roles gives 0.53 baseline.

STRATEGY UPDATE: Since OpenRouter has no credits, I will:
1. Focus on the scripted mining improvements (element-aware, round-robin) which work WITHOUT the LLM
2. Use `machina_roles` or `class=machina_llm_roles,kw.scripted_miners=true` with LLM disabled
3. The mining skill improvements are in the scripted skill execution layer, not the LLM prompt
4. This is actually the RIGHT approach per the issue: "bigger failures are in skill execution"

The issue metric is:
- Primary: hearts created via make_heart > 3 per 1000 steps
- Secondary: element deposit ratio within 2:1 balance (vs current 30:1)
- Reward target: > 0.80/agent at 1000 steps with 2A1M

---

## 2026-03-29T: starting to run baseline

Running scripted baseline (machina_roles, 4 agents all aligners) to establish current reward:
- machina_roles 4A: 0.53 reward

Also checking current mine_closest behavior for reference.

---

## 2026-03-29T: baseline result is

Scripted `machina_roles` with 4A: **0.53 reward** (no mining, all aligners)
Scripted `machina_roles` with 3A+1M: Need to test

The previous session from autoresearch_22_march showed:
- Best 1000-step result: 2.260 (3 LLM aligners, no miners)
- Best 2000-step result: 1.24 (4 LLM aligners, no miners)
- LLM is disabled now due to API credits issue

Without LLM, we'll focus on improving scripted miner behavior for element balance.
The issue's success criteria (make_heart > 3 per 1000 steps) requires:
- Miner deposits balanced resources
- Hub can craft hearts from those resources
- Aligners can use those hearts

Since the LLM is down, I'll test with `class=machina_llm_roles,kw.scripted_miners=true,kw.num_aligners=3`
which uses scripted miners with LLM aligners. The LLM will timeout and use scripted fallback.

---

## Experiment Loop

