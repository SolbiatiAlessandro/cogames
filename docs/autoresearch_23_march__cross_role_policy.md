# Autoresearch 23 March — Cross-Role Policy

Branch: `autoresearch_23_march__cross_role_policy`

**Setup:** `cogsguard_machina_1.basic`, 1000 steps, 8 agents (`class=machina_llm_roles,kw.num_aligners=3`), seed=42, local LLM (nemotron-nano-9b-v2 via vLLM), action-timeout-ms=3000

---

## 2026-03-23T: Session start

**Context from autoresearch_22_march:**
- Best 1000-step result: **0.92** (commit `7321afc`) with 3 LLM aligners + 5 LLM miners
- Best 2000-step result: **1.24** (commit `6857db1`) with 4 aligners only
- Current policy is **role-hardcoded at init**: aligner agents only do aligner skills, miner agents only do miner skills
- We have a successful miner economy (miners deposit → hub crafts hearts → aligners align)
- Known bottlenecks at 0.92 (1000 steps): 24 align_neutral timeouts + 26 get_heart timeouts = ~5000 wasted aligner steps

**Direction:**
The next unlock is making the policy **role-independent**. Instead of "I am an aligner, choose aligner skill", ask "what does the team need now?". Key ideas:
1. Ask LLM: "what does the team need now?" and let agents dynamically choose role
2. If lots of resources and no one aligning → switch to aligner
3. If enemy junction appears → switch to scrambler
4. Cross-role awareness: agents can re-gear at stations
5. Better debug: log full state on "unstuck" events
6. Two-tiered LLM: 4B nano for simple decisions, larger model (liquid/lfm-2-24b-a2b) for strategic decisions

**Plan:**
1. Run baseline (1000 steps, 8 agents, 3 aligners, local LLM)
2. Add unstuck debug logging
3. Implement cross-role prompt: unified skill set spanning all roles
4. Experiment with team-state summary in prompt
5. Try two-tiered LLM if time permits

---

## Experiment Log

### Baseline — 0.45 — 8 agents (3 aligners + 5 miners), cloud LLM

**Result:** mission_reward=0.45, junction.aligned_by_agent=0.62 (5 total), heart.gained=0.75/agent (6 total), death=1.25/agent (10 total), max_stuck=122.75

Command: `LOCAL_LLM_MODEL_PATH= cogames run -m cogsguard_machina_1.basic -c 8 -p class=machina_llm_roles,kw.num_aligners=3,kw.llm_model=nvidia/llama-3.3-nemotron-super-49b-v1.5 -e 1 -s 1000 --action-timeout-ms 10000 --seed 42`

**Key observations:**
- Total held-steps: 0.45 × 8000 = 3600 — same as 0.92 × 4000 = 3680 (4-agent old best)
- The per-agent reward is diluted because 5 miners don't contribute to junction holding
- Deaths are high (10 total) — agents spending time in enemy territory
- Cross-role key insight: if miners switch to aligners after depositing, all 8 agents earn held-steps → 2-3x reward boost

**Cross-role hypothesis:** With 8 cross-role agents, each starting as miner then switching to aligner:
- Phase 1: miners gather resources fast (8 miners vs 5 miners → much faster)
- Phase 2: agents switch to aligner → 7-8 aligners can hold all 7 junctions
- Target: 7 junctions × 700 steps × 8 agents = 4900 held / 8 = 0.61 minimum, but multi-alignment cycles could push to 1.5+

