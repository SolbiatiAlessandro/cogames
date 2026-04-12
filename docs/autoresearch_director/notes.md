# Director Notes
_Written: 2026-04-12 (Session 6)_

## What I observed in the replays

Analyzed 5 online replays: our best (7.68 vs scissors), our worst (0.30 vs shweta), our self-play qualifying (1.59), dinky's best (43.75 vs Paz-Bot), and one slanky match.

### Our BEST match (7.68, cross_role_full_v8 vs scissors_v1_v13)
- Agents 0-3 (scissors): 7800-8900 action_id entries, 7400-8800 moves — extremely active
- Agents 4-7 (us): 148-282 action_id entries, 0-160 moves — **barely acting**
- Agent 7 emitted 148 change_vibe actions and 0 moves. We are freeloading on scissors.
- heart.gained=10.4/agent, but cogs/heart.withdrawn=5 (only initial hub hearts consumed)
- 582 carbon deposited, 78 carbon withdrawn (=11 make_hearts crafted but unclaimed)

### Our SELF-PLAY (1.59, qualifying)
- 53% move failure rate (5289 failures/agent vs 4711 successes)
- Only 1 of 8 agents got aligner gear (aligner.gained=0.12/agent)
- 5 agents got miner gear, 1 got scrambler (contamination), 1 got scout
- Total deposits: 17 elements across all 8 agents in 10k steps — near zero mining
- Only 4 junctions aligned, 342 unique cells visited per agent
- 27 total agent deaths

### dinky BEST match (43.75, vs Paz-Bot-9000) — the reference target
- 9822 move successes/agent with 146 failures (1.5% failure rate!)
- heart.gained=56.6/agent (453 total hearts!)
- 3244 carbon deposited, 448 carbon withdrawn (=64 make_hearts)
- 220 junctions aligned, 437k junction-ticks held
- 2468 unique cells visited/agent, max distance 77.5 from spawn
- 3.25 aligner gear gained per agent (agents switch roles multiple times)
- 0 change_vibe actions (like all other policies — vibes set by station stepping)

### Key insight: change_vibe_* is a non-issue
Every policy (ours, dinky, slanky, scissors) shows 0 change_vibe actions in action_id. The `action.change_vibe.success` counter tracks automatic gear changes from stepping on stations. Issue #31 is resolved — not a bug, just how the game works.

## Current bottleneck

**Heart pipeline throughput is the #1 gap.** dinky gains 56 hearts/agent vs our 10 — a 5.4x gap that directly maps to the 5.7x score gap (43.75 vs 7.68). Our agents deposit resources and some make_hearts get crafted, but the hub_depleted logic from issue #16 blocks agents from withdrawing crafted hearts. This is the single highest-leverage fix.

**Move failure rate is #2.** In self-play: 53% failure vs dinky's 1.5%. This effectively halves our throughput. In cooperative matches with strong partners, our failure rate drops to 4.5% — suggesting agent-agent congestion is the primary self-play driver, with invisible extractors as secondary.

**Action throughput is a structural constraint** but not directly fixable: our LLM policy decides less frequently than RL-trained policies. The lever is to make each decision count more (fewer failed moves, better skill choices, faster transitions).

## What I expected to happen vs. what I found

**Expected (from session 5 notes):** Hybrid config (cross_role aligners + scripted miners) would push 8-agent to ~0.60/agent. gemma-3-12b might scale.

**Found:**
1. Issue #28 researcher DID fix qualifying crash and got cross_role into competition. 3A5M all-LLM scores 1.61/agent offline at 10k — a solid result. Competition avg is 2.94 online.
2. The hybrid config question is now moot — all-LLM beats scripted miners by 20% at 10k (1.61 vs 1.34). HTTP pooling + retry removal made all-LLM stable.
3. But the REAL problem is 8.5x behind dinky. The offline optimizations (make_heart, hub depletion) work at 1000 steps but decay at 10k. Hearts are crafted but not withdrawn.
4. No one tested the "gemma-3-12b + 8 agents" question from session 5. Gemma was tried at 3 agents (0.70, +24%) but the researcher pivoted to fixing the qualifying crash (right call).

## Issues updated this session
- **#28**: Branch merged to main. Competition results verified. Kept in-progress for score target.
- **#34 (NEW)**: Heart Pipeline Throughput — priority:1. The 5.4x gap to dinky.
- **#35 (NEW)**: Move Failure Rate — priority:1. The 53% failure rate crisis.
- **#31**: priority:1 → priority:3. change_vibe is not a bug; no policy uses it.
- **#32**: priority:1 → priority:3. Partner variance affects dinky too; absolute perf matters more.
- **#30**: priority:1 → priority:2. Partially fixed by #28; residual tracked by #34/#35.
- **#12**: priority:2 → priority:3. Gear acquisition works in most matches; secondary to throughput.
- **#25**: kept at priority:2. 8-agent scaling is relevant but subsumed by #34/#35.

## Priority stack for OpenClaw
```
priority:1  #34  Heart Pipeline Throughput (5.4x gap)         <- SPAWN NEXT
priority:1  #35  Move Failure Rate (53% vs 1.5%)              <- SPAWN NEXT
priority:1  #29  10k Step Eval Alignment                      <- after #34/#35
priority:1  #28  Qualifying Crash Fix (in-progress)           <- monitoring
priority:2  #30  8-Agent Self-Play Collapse
priority:2  #25  8-Agent Scaling
priority:2  #24  Balanced Mining Strategy
priority:2  #27  Andre Von Huck suggestions
priority:2  #26  shweta policy analysis
priority:2  #20  Coordinated Exploration
priority:2  #19  LLM Code Gen
priority:2  #17  LLM Skill Validation
priority:2  #21  Intrinsic Motivation
priority:2  #11  Active Inference
priority:2  #10  Role Tuning
priority:3  #31  change_vibe (non-issue)
priority:3  #32  Partner robustness (secondary)
priority:3  #12  Gear Acquisition (secondary)
priority:3  #23  Meta-Learning
priority:3  #22  Social Influence
```

## Open questions for next director
1. **Heart withdrawal mechanics**: `cogs/heart.withdrawn: 5` in ALL replays (ours AND dinky). Yet dinky's agents gain 56 hearts each. How? Is `heart.withdrawn` only counting initial hub hearts, while make_heart hearts are distributed automatically? Or do agents pick up hearts by stepping on the hub (no explicit action needed)?
2. **Action_id sparsity**: dinky agents show 1200-5000 action_id entries but `action.move.success: 9822`. Is action_id delta-encoded (only logs changes)? If so, our 148-282 entries may represent more actual activity than it looks.
3. **Online map differences**: maps appear to vary (67-68 junctions, 3185-3330 walls). Are online maps randomized per match? This affects navigation reliability.
4. **v9 improvements**: The #28 researcher mentioned hazard-avoidance for miner nav + fast-path skill transitions as ready but not uploaded. Where is this code? Should the next researcher pick it up?
5. **Why does our cooperative failure rate (4.5%) differ so much from self-play (53%)?** If it's purely congestion, agent dispersion (#35 Experiment B) is the highest-leverage fix. If it's something about how the partner's agents interact with the environment (e.g., clearing extractors), that's a different problem.
