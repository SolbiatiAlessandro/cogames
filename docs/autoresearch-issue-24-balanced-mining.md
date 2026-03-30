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

### v3 (50b915f): 0.590 - Element-aware mining with 30-step near-hub search

First real balanced miner: detects which element is lowest in inventory and targets that type's extractor.
- Si deposits = 1 (still unreachable - only near-hub search, Si far from hub)
- O deposits = 11, C deposits = 21, Ge deposits = 21
- Full-map exploration fallback added for when target element not found after timeout

### v4 (1b7b530): 0.603 - Approach-cell hub deposit + full-map exploration

Critical bug fix: Hub is a "blocked object" so BFS returns None when navigating to it directly.
Fixed by approach-cell strategy: navigate to adjacent free cell then step INTO hub.
Also switched to full-map _explore for Si discovery (Si too far for near-hub search).
- Si deposits = 21 (found via full-map explore), but O at (-31,10) is in enemy territory -> miner dies

### v5 (34f4b60): 0.623 - Unreachable extractor tracking

Prevents death loop to enemy oxygen extractor at (-31, 10).
After 15 steps navigating to same extractor, marks it unreachable.
When all known extractors of a type unreachable, immediately falls back to mine_until_full.
- O deposits still ~8-10 avg (near-hub O not found when enemy O marked unreachable)
- Reward gap: 0.623 vs target 0.80

### v6-v8: Session 2 findings

2026-03-29: Session 2 began. Key findings:

**Heart crafting mechanics understood:**
- make_heart handler requires hub has 7 of EACH element (oxygen, carbon, germanium, silicon)
- Aligner triggers make_heart by moving INTO hub when hub has 0 hearts but 7+ each element
- get_and_make_heart triggered when hub has 1 heart + 7 each element (best case: give agent heart AND craft)
- Gear costs drain hub: aligner equip = {C:3,O:1,Ge:1,Si:1} per equip. With 4 aligner equips = 12C consumed!
- Hub initial C = 9 only. 9 - 12 = -3 C deficit before any mining! Miner must deposit 7+ C just to enable heart crafting.

**Aligner stuck loop (800+ steps) explained:**
- Hub has 0 hearts + C<7: make_heart can't trigger (not enough C for 7 threshold)
- Aligner tries hub every step: deposit(fails), get_heart(fails), get_and_make_heart(fails), get_last_heart(fails), make_heart(fails for C<7)
- Aligner is stuck at hub indefinitely until miner deposits enough C

**v7: avoid_hazards=True in _get_heart**
- Fixed: when navigating to hub for hearts, avoid other gear stations in BFS path
- Prevents stuck loops where BFS routes through gear station approach cells
- Result: seed 0 aligner stuck steps 714->1, reward 0.601->0.609

**v8: SharedMap per-element extractors**
- Added known_carbon/oxygen/germanium/silicon_extractors to SharedMap
- Miner's per-element extractor knowledge now persists across death/respawn
- No measurable reward improvement for seeds 0-4 (those seeds don't have enough miner deaths)
- Correctness improvement for multi-death scenarios

**5-seed benchmark (seeds 0-4):**
- v7: avg 0.618 over seeds 0-4
- High variance: seed 2 = 0.704, seed 7 = 0.46

**Key blockers remaining:**
1. Carbon deficit: hub C consistently depleted below 7 by gear costs
2. Low-seed miner failures: miner in bad seeds (6,7) barely deposits
3. Oxygen bottleneck: only ~10 O per run due to enemy territory

### v6: Safe search after unreachable extractors

2026-03-29: starting new experiment loop. Want to try: when all known oxygen extractors are marked
unreachable (e.g., enemy O at -31,10), instead of immediately falling back to mine_until_full,
do a near-hub _explore_near_hub search for up to 40 steps to try to find a SAFE oxygen extractor.
The v3 experiment found oxygen via near-hub search, so this should recover safe O.
Hypothesis: this will increase O deposits from ~8-10 to ~15-20, improving reward from 0.623 toward target 0.80.

Added constant: _SAFE_SEARCH_AFTER_UNREACHABLE = 40

---

## 2026-03-30T00:00: Session 3 continues - experiment v9 per-element search timeouts

Resuming autoresearch session. Last session found:
- v8 baseline: avg 0.653 over seeds 0-2
- Multiple v9 variants discarded: weighted carbon, lower return_load=16, early deposit
- Key insight: silicon is consistently under-deposited (Si.dep=4 in seed 0 vs C.dep=10, O.dep=10, Ge.dep=10)
- Germanium also takes long to find in some seeds

Plan for v9: per-element search timeouts
- Carbon and oxygen: fast to find, keep _SEARCH_TIMEOUT=80
- Germanium and silicon: hard to find, increase to 160 steps
- Hypothesis: miner will spend more time searching for Si/Ge instead of giving up and doing mine_until_full (which might get O or C again)

Implementation:
- Replace `_SEARCH_TIMEOUT = 80` with dict `_SEARCH_TIMEOUT_BY_ELEMENT = {"carbon": 80, "oxygen": 80, "germanium": 160, "silicon": 160}`
- Update `_mine_balanced` to use `self._SEARCH_TIMEOUT_BY_ELEMENT.get(target_elem, 80)` instead

**Result v9a: 0.609/0.647/0.704 = avg 0.653** - same as v8! Per-element timeout doesn't help.
Reason: silicon is limited by miner death (carrying 10 Si but hub only gets 4) rather than search time.
The miner fills to 28 total (return_load) with only 4 Si because Si extractors are far; miner accumulates C/O/Ge while searching for Si.

**New insight: single-element trips would be better.**
Instead of balanced trip (7C+7O+7Ge+7Si=28), do separate focused trips:
- Trip 1: mine only carbon until 7, then deposit
- Trip 2: mine only oxygen until 7, then deposit
- Trip 3: mine only germanium until 7, then deposit
- Trip 4: mine only silicon until 7, then deposit
- Hub has 7 of each -> make_heart!

This prevents partial deposits (Si.dep=4) because the miner only deposits AFTER getting enough Si.
Also reduces death risk (smaller load = faster deposit trips = less time in enemy territory).

But wait: if miner focuses ONLY on Si for all 160 steps searching, and Si is in enemy territory, it will die with 0 Si. The partial balanced approach at least gets C/O/Ge deposited which is useful too.

Alternative: **hub element tracking** - track which element the hub needs MOST (compare hub amounts to 7 threshold), and send miner for that element. But we can't observe hub inventory directly from agent POV.

Actually we can track it via our deposits! Each deposit trip deposits ~7 of one element. We can count how many of each we've deposited and infer hub needs.

## 2026-03-30T01:00: v11 aligner improvements - heart timeout + patrol + move_blocked fixes

Started analyzing why aligners get stuck for 700-800 steps in some seeds.

**Key findings:**
1. Aligner gets stuck at hub approach cell waiting for hearts that never come (hub out of hearts)
2. The aligner's `move_blocked_cells` gets poisoned by failed hub/junction attempts
3. Periodic reset of `move_blocked_cells` (every 100 steps) + blocked_cells cleanup helps partially
4. Junction cells not added to `move_blocked_cells` prevents blocking BFS paths through junction areas

**v11 changes to aligner_agent.py:**
- `_GET_HEART_TIMEOUT = 50`: after 50 steps waiting for heart, switch to patrol mode
- `_navigate_to_any_junction()`: navigate to nearest junction (friendly/enemy/neutral) when heartless
- Junction cells excluded from `move_blocked_cells` tracking (dynamic obstacles)
- Periodic `move_blocked_cells` + `blocked_cells` reset every 100 steps

**Results:**
- Seeds 0-2: IDENTICAL to v8/v9 (0.609/0.647/0.704 = avg 0.653)
- Seeds 3-5: similar to v8/v9 (~0.55-0.58)
- Seed 6: slight improvement 0.469 -> 0.501 (both aligners still stuck 756/800 steps)
- Seed 7: similar to v8

**Root cause analysis:**
The stuck behavior happens when:
1. Aligner reaches hub approach cell
2. Hub has no hearts (make_heart not triggered yet)
3. Aligner tries to move into hub (fails), adds hub to move_blocked_cells (redundant but OK)
4. With heart timeout (50 steps), aligner switches to patrol_junctions
5. patrol_junctions calls _navigate_to_any_junction
6. BFS finds path to nearest junction, but path cells might be blocked by move_blocked_cells accumulated from earlier failures
7. Greedy fallback picks direction toward junction which is a wall -> move fails
8. More cells added to move_blocked_cells -> BFS more poisoned

The fix works partially: with junction cells excluded from move_blocked, BFS can route around (not through) junctions. With periodic reset, stale blocks are cleared. But in some seeds (6), the hub area's specific topology traps both aligners.

**Conclusion:** v11 changes give same reward for seeds 0-2 (primary benchmark) and slight improvements for hard seeds. Keeping the changes since they don't hurt and might help.

## 2026-03-30T01:30: shifting focus - what can actually improve reward?

The aligner stuck issue is well-understood but fixing it doesn't improve seeds 0-2 (which are already near their ceiling with current alignment strategy). Need to think about what ELSE can improve reward.

Key observation from seed 2: carbon.deposited=20, oxygen.deposited=20, germanium.deposited=20, silicon.deposited=0 yet reward=0.704. The miner deposited C/O/Ge but no Si in seed 2! And reward is the BEST of all seeds tested. This suggests silicon deposits matter less than alignment.

The aligner is the bottleneck, not the miner. More junctions aligned = more reward. The miner just enables more hearts for aligners.

What limits junction alignment?
1. Aligners only align 3-4 junctions per episode before losing hearts
2. Clips recapture junctions faster than aligners can re-align
3. Hub area access: some aligners get trapped near hub

Possible improvement: **improve how aligners decide which junctions to align**. Currently they go to the nearest neutral junction. Maybe going to a STRATEGIC junction (one that is close to hub/friendly territory AND far from enemy spawn) would hold longer.

Or: **improve aligner recapture of enemy junctions**. After clips take junctions back, aligners should prioritize recapture of recently-lost junctions.

Or: **aligner HP management** - when low HP, retreat to hub area instead of dying and losing gear.

## 2026-03-30T02:00: v12 idea - smarter aligner junction selection

Current: aligner goes to nearest neutral junction
Problem: some junctions are in bad positions (far from hub, easy for clips to recapture)

Idea: bias toward junctions that are:
1. Closer to friendly territory (hub/other friendly junctions)
2. Further from clips' spawn area

Not easy to implement without knowing clips spawn position. Skipping this.

Alternative idea: **track junction hold time** - prefer junctions that we've held before (we know the path, clips don't focus on them as much). But this requires persistent state between trips.

Actually, the simplest improvement: go to 2 junctions at once (if close), hold both longer.

Conclusion: Aligner improvements are hard without knowing enemy spawn positions. Focus on current approach and accept ~0.653 avg for seeds 0-2 as the ceiling.

## 2026-03-30T03:00: starting new experiment loop - v12 patrol hub-return pulse

In this experiment I want to try: fix a critical bug in patrol mode. When aligner's `get_heart_steps >= _GET_HEART_TIMEOUT (50)`, it switches to patrol_junctions mode. But once in patrol, `get_heart_steps` NEVER resets unless the aligner has a heart in inventory. The only way to get a heart is to visit the hub. But in patrol mode, aligner is GOING AWAY FROM HUB. So the aligner is permanently stuck in patrol mode with no hearts and can never align!

My hypothesis: adding a "patrol hub check" every 40 steps of patrol will allow aligners to pick up newly-crafted hearts (from miner's element deposits triggering make_heart). This will let aligners that previously patrolled forever to resume aligning junctions, improving held junction time and thus reward.

Implementation:
- Add `_PATROL_HUB_CHECK = 40` constant (steps between hub checks during patrol)
- Add `patrol_steps: int = 0` field to AlignerState
- In step_with_state: when in patrol mode, increment patrol_steps. When patrol_steps reaches _PATROL_HUB_CHECK, reset get_heart_steps to 0 (forces hub check) and reset patrol_steps.

