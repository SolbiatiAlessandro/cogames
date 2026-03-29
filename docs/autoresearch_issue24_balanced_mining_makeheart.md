# Autoresearch Issue 24: Balanced Mining Strategy for make_heart Cycle Optimization

Branch: `autoresearch/issue-24-balanced-mining-makeheart`

**Issue**: https://github.com/SolbiatiAlessandro/cogames/issues/24

**Setup:** `cogsguard_machina_1.basic`, 1000 steps, `class=machina_llm_roles`, seed=42, cloud LLM (nvidia/llama-3.3-nemotron-super-49b-v1.5 via OpenRouter)

## Success Criteria (from issue)

Primary metrics:
- hearts created via make_heart > 3 per 1000 steps with 1 miner (vs current 0-3)
- Element deposit ratio within 2:1 balance (vs current 30:1 imbalance)
- Total reward > 0.80/agent at 1000 steps with 2A1M configuration

## Context from Issue

The issue states make_heart requires 7 of EACH of 4 elements (28 total). Previous runs show skewed deposits:
- 3A1M: 1/10/1/30 (Ge/C/Si/O) = 0 hearts made (need 7 of each)
- main 2A1M: 20/21/1/0 = 0 hearts (no oxygen deposited)
- v13 seed 42: 20/22/4/1 = 3 hearts (good Ge+C but low Si+O)

Map has: 37 carbon, 35 germanium, 33 silicon, 40 oxygen extractors. Miners visit 1-2 types (nearest ones).

## Plan

My approach:
1. Run baseline first to understand current state
2. Implement element-tracking in miner state to know which elements are least deposited
3. Implement element-aware `mine_balanced` skill that directs miner to rarest-element extractors
4. Track per-element inventory counts and deposit counts
5. Try round-robin element extraction to ensure balance

Key challenge: the miner needs to know what type of element each extractor produces, and also know the current hub deposit counts to determine what's rarest.

---

## 2026-03-29T00:00: autoresearch starting, my plan is to...

Implement element-aware balanced mining. The core insight is that make_heart needs 7 of each of 4 elements. Current miners go to nearest extractor regardless of type, causing heavy skew. I'll:

1. Track extractor element types as miners discover them
2. Track per-element deposit counts
3. Add a `mine_balanced` skill that prioritizes the least-deposited element type
4. Possibly add round-robin extraction as a simpler fallback

The tricky part is knowing what element an extractor produces - need to read it from observation tokens.

## 2026-03-29T01:30: Experiment A results

Ran 3 configurations with `nvidia/nemotron-nano-9b-v2:free` at 1000 steps, seed=42, 2A1M:

1. WRONG baseline (2A+scout, not 2A+miner): reward=0.66 (but agent 2 was scout not miner!)
2. Element-aware LLM mining (2A+1LLM_miner): reward=0.51, germanium.gained=3.67
3. Scripted miners (2A+1scripted_miner): reward=0.68, silicon.gained=4.33, junction.aligned=2.67

Key findings:
- Scripted miners outperform LLM miners (0.68 vs 0.51) because LLM adds latency
- The miner IS depositing with element-aware code, but only single element types
- The deposit is still unbalanced: germanium deposited but not other elements
- Scripted miners also only deposit silicon (not balanced)
- Neither approach crafts hearts from deposits (need 7 of EACH element)

The element-aware targeting IS working (we saw `known_extractors_by_element: carbon=4, oxygen=2, germanium=3, silicon=7`
and the miner targeting the rarest element). But 1000 steps + large map means the miner
can only do 1-2 complete mine+deposit cycles. Not enough to get 7 of each element.

ROOT CAUSE: The return_load=40 means miner mines 40 items total per cycle. With 4 elements,
that's on average 10 per element per cycle. After 1 deposit cycle, deposit counts might be
carbon=10, oxygen=10, germanium=10, silicon=10 (balanced, totaling 40).
But make_heart needs 7 of each = 28 total. So 1 cycle SHOULD be enough if balanced!

The real issue: the miner is targeting the LEAST-deposited element, which is correct logic.
But the miner can only carry 40 items total, and the hub needs 7 of each (28 total).
If the miner fills all 40 slots with the same element (because that element's extractor
is closest), we only deposit 40 of one type but 0 of others.

Wait - the miner is using `mine_until_full` which navigates to ONE extractor and mines until full (40 items).
All 40 items will be the SAME element type. So a single full load = 40 of one element.
We need at least 7 deposits (one per element * 4, but 4 half-loads) to get 28 total balanced.

CRITICAL INSIGHT: The element-balance target selection only works at the SKILL SELECTION level
(which extractor to go mine at). But the miner mines 40 items of the SAME type per trip.
To get 7 of each, the miner needs 4 separate trips (one to each element type), carrying
at most 40 items per trip.

For make_heart to work: 4 separate mining trips minimum (one per element type).
At ~200-300 steps per trip (gear up + navigate + mine + return), that's 800-1200 steps minimum.
1000 steps is barely enough for one cycle to work.

Better approach: Lower the `return_load` threshold to 10 items (trigger deposit after 10 items)
so the miner makes MORE trips but carries LESS, depositing more diverse elements over time.

OR: Implement multi-element collection (mine different elements in one trip before depositing).

---

## 2026-03-29T00:05: starting to run baseline

Running 2A1M configuration (2 aligners + 1 miner) at 1000 steps to see current performance.

Command: `cogames run -m cogsguard_machina_1.basic -c 3 -p class=machina_llm_roles,kw.num_aligners=2 -e 1 -s 1000 --action-timeout-ms 10000 --seed 42`

## 2026-03-29T00:15: baseline result is 0.66 reward

Baseline: 0.66 reward, aligned=7 junctions (junction.aligned_by_agent=2.33/agent), held=5550, heart.gained=2.33/agent.

Key observations:
- Silicon.gained: 1.00/agent (only 3 total) - miner barely deposited anything
- status.max_steps_without_motion: 415 - very high, agents stuck
- action.move.failed=802 vs action.move.success=197 - terrible navigation (80% fail)
- The 2A1M config doesn't have the move-failure tracking working well

This baseline is MUCH worse than the 4A configuration (1.24 at 2000 steps).
The issue is that at 1000 steps, the 2A1M config barely aligns any junctions.

Key finding: the miner deposited almost nothing - only 1 silicon per agent.
This means balanced mining is moot if the miner can't even deposit.

Looking at the issue success criteria: "Total reward > 0.80/agent at 1000 steps with 2A1M configuration"
This is actually a hard target given current 0.66.

IMPORTANT NOTE: The baseline command `class=machina_llm_roles,kw.num_aligners=2` was WRONG.
The 3rd agent was being assigned as a SCOUT, not a MINER. The scout earns 0 reward.
Correct 2A1M config: `class=machina_llm_roles,kw.num_aligners=2,kw.num_scouts=0`

ALSO: The paid OpenRouter model `nvidia/llama-3.3-nemotron-super-49b-v1.5` is giving 402 errors.
Using free model `nvidia/nemotron-nano-9b-v2:free` instead.

## 2026-03-29T00:20: starting new experiment loop - Experiment A: Element-Aware Mining

My plan: Implement per-element extractor tracking in SharedMap and MinerSkillState.
The miner will track which extractors produce which element, count deposits per element,
and prefer to mine from the rarest-deposited element type.

Hypothesis: If miner balances element collection (7+ of each), hub will craft hearts from
deposited resources. More hearts = more junction alignments = higher reward.

But first I need to verify: can the miner even deposit resources effectively?
The baseline showed silicon.gained=1/agent which is very low. Need to fix navigation first.

Looking at the autoresearch_22_march.md, the key fix was move-failure tracking which was
confirmed to drop max_steps_without_motion from 965 to 11. Let me check if that's still
working in current code...

In aligner_agent.py line 363-365 I can see the move-failure tracking IS implemented.
And in llm_skills.py line 170-174 it's also implemented for miners.

The issue in the baseline might be:
1. The miner can't navigate back to hub after mining (the deposit_to_hub issue)
2. The miner is spending too many steps stuck

Let me try a focused experiment: improve the mining loop efficiency first by adding
element-aware targeting in the mine_until_full skill.

