# Autoresearch Issue 24: Balanced Mining Strategy for make_heart Cycle Optimization

Branch: `autoresearch/issue-24-balanced-mining`

**Setup:** `cogsguard_machina_1.basic`, 1000 steps, 3 agents (2A1M), `class=machina_roles,kw.num_aligners=2`, seed=42, scripted policy (no LLM - OpenRouter credits exhausted)

**Issue context:**
- make_heart requires 7 of each of 4 elements (28 total)
- Current miners deposit heavily skewed resources (e.g., 30 oxygen + 10 carbon + 1 germanium + 1 silicon)
- This means 0 hearts crafted even with tons of resources deposited
- Fix: direct miners to balance element collection

**Success criteria from issue:**
- hearts created via make_heart > 3 per 1000 steps with 1 miner
- Element deposit ratio within 2:1 balance (vs current 30:1 imbalance)
- Total reward > 0.80/agent at 1000 steps with 2A1M configuration

---

## 2026-03-29T00:00: autoresearch starting, my plan is to...

Starting autoresearch for issue 24. My plan is:
1. Understand current miner behavior (StarterCogPolicyImpl goes to closest extractor, causing type skew)
2. Run baseline to confirm current element imbalance
3. Implement element-aware mining: track which element types have been collected, target the rarest
4. Experiment with round-robin extraction: visit one extractor of each type per trip
5. Try deposit threshold: only return when carrying at least 7 of each element

Key technical insight: the `_extractor_tags` in StarterCogPolicyImpl is the union of all 4 element types. The fix needs to:
a) Detect individual element types via separate tag lookups
b) Track how many of each element is carried
c) Navigate toward the most-needed element type's extractor

The MinerSkillImpl in llm_skills.py already has `_inventory_counts` which breaks down inventory by element type. The key is to modify `_mine_until_full` to prefer extractors of the deficit element type.

Note: OpenRouter API key returned 402 Payment Required - must use scripted policy only (no LLM). This means we'll work with `machina_roles` (scripted) and focus on improving the miner skill in the scripted layer.

---

## 2026-03-29T00:01: starting to run baseline

Running baseline: 2 aligners + 1 miner, scripted, 1000 steps, seed 42.

Baseline result: **reward = 0.39**
- junction.aligned_by_agent = 1.33
- heart.gained = 1.67/agent
- heart.withdrawn = 4 (from hub initial supply of 5)
- cogs/carbon.amount = 8 (in hub, not withdrawn)
- cogs/oxygen.amount = 10
- cogs/germanium.amount = 8
- cogs/silicon.amount = 12
- No "deposited" metric visible = no deposits completed by miner!
- status.max_steps_without_motion = 649 (high - lots of stuck behavior)

Key observation: The miner (StarterCogPolicyImpl) just targets closest extractor and mines indefinitely - never deposits! The deposit action requires reaching the hub. With max_steps_without_motion=649, the miner is stuck.

The current scripted miner in MachinaRolesPolicy uses StarterCogPolicyImpl with preferred_gear="miner" which just heads toward nearest extractor and never deposits. It has no deposit logic at all!

So the issue is even worse than described: the scripted miner doesn't even implement deposit. The MinerSkillImpl (in llm_skills.py) DOES implement deposit via mine_until_full + deposit_to_hub cycle, but that requires LLM or the scripted skill dispatch from LLMMinerPolicyImpl.

**Plan revision:** Need to either:
a) Use LLMMinerPolicyImpl (scripted mode) as the miner - it has mine_until_full + deposit cycle
b) Create a new balanced miner policy that uses MinerSkillImpl with element awareness

The `machina_llm_roles` policy with `scripted_miners=true` would use LLMMinerPolicyImpl with no LLM (scripted skill dispatch). Let's try that.

---

## Experiment Loop

