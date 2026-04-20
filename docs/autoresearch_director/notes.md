# Director Notes
_Written: 2026-04-20 (Session 13)_

## What I observed in the replay

Replay from session 10 (April 18) — cannot run new captures (mettagrid not installed in this env):
- 4 agents, 500 steps. A0 and A1 are actively mobile. A2 and A3 are **stuck** from step 100-200 onwards.
- A3 at position (26,76) doesn't move at ALL after step 100. A2 at (47,82) is frozen from step 200+.
- Reward growth is linear at 0.08/step (from junction holding) — no acceleration, indicating no additional junctions being gained after initial gear-up.
- Only the hub area (center) shows agent activity. Map corners/edges with junctions are unreached.

## Current bottleneck

**Miner productivity plateau at ~5k steps** is the primary bottleneck now.

Evidence chain:
1. `hub_deposits_total` bug fixed (aRnlF) — miners no longer stuck after first deposit
2. Depleted extractor adjacency bug fixed (Fb3vU) — miners no longer loop to depleted extractors
3. But ALL nearby extractors deplete by ~5k steps, causing a NEW freeze
4. Junctions plateau at 73/10k (up from 47 pre-fix, but far from RL's ~500)
5. The 10x deposit gap vs RL (1456 vs ~14,000) is the quantitative expression of this

Agent mortality is FIXED offline (0 deaths in v21+ runs with HP retreat 0.70). The "mortality crisis" was actually a productivity crisis masquerading as deaths.

## What I expected to happen vs. what I found

**Expected** (from session 12 notes): v34 crash would be diagnosed, agent mortality would be the focus.

**Found**:
- v34 crash was already fixed (v35 uploaded by researcher on Fb3vU branch) — #43 closed
- Agent mortality was fixed by hub_deposits_total restoration (miners actually mine → hearts get crafted → agents survive)
- The REAL bottleneck shifted downstream: extractors deplete and miners have no exploration strategy for finding fresh ones
- ccN7G researcher found that several offline improvements (nav_shake, stuck_threshold=12, dynamic_return_load) were WORSE online — important offline-to-online gap data

## Branches merged this session

1. **aRnlF** (fast-forward): hub_deposits_total fix + miner element diversification. +40% at 10k. Clean merge.
2. **ccN7G** (conflict resolved in llm_miner_policy.py): Role allocation fix (critical online), junction sharing, explore cap. Online-tested reverts included (nav_shake, threshold, return_load).
3. **Fb3vU** (conflict resolved in llm_skills.py): Depleted extractor adjacency fix, hazard-safe greedy, HP retreat 0.70. +55% junctions at 10k.

## Issues updated this session

- **#43**: CLOSED — v34 regression resolved (v35 uploaded with httpx fix)
- **#42**: CLOSED — httpx import issue fully resolved in codebase
- **#39**: CLOSED — submission process operational (13 entries on leaderboard)
- **#36**: Commented with merge status. Mortality largely fixed offline. Remaining work is submitting v37 online.
- **#40**: Commented with Fb3vU merge and remaining 10x gap analysis.
- **#44**: CREATED (priority:1) — miner productivity plateau at ~5k steps. New primary research target.

## Priority stack for OpenClaw

```
priority:1  #44  Miner productivity plateau    <- SPAWN NEXT (new, highest leverage)
priority:1  #36  Agent mortality               <- submit v37 online, validate
priority:1  #41  RL policy training            <- BLOCKED (needs GPU)
priority:2  #40  Mining throughput             <- subsumed by #44
priority:2  #27  Andre Von Huck / A*           
priority:2  #24  Balanced Mining               
priority:3  #38 #32 #31 #30 #26 #12 #10-#23   <- deprioritized
```

## Open questions for next director

1. **Does v37 improve online score?** The Fb3vU depleted-extractor fix + hub fix should significantly help. Need to submit and monitor. API was 503 today — retry next session.

2. **Offline-to-online gap learnings from ccN7G**: nav_shake was +7.5% offline but catastrophic online. stuck_threshold=12 was +9% offline but worse online (v24 with threshold=20 ranks higher). Why? Hypothesis: offline runs are 500-1000 steps with fixed seed; online is 10k steps with diverse opponents. Aggressive parameters help short runs but hurt long-term stability.

3. **Is the 5k freeze universal?** Only tested on seeds 42-44 at 10k steps. Need more seeds + different maps to confirm the plateau is structural (extractor density) vs. seed-specific (map layout).

4. **dtLLg branch (ship-proximity retreat)**: Not merged — all experiments were online-only with no offline validation. Should be submitted as next tournament version after v37 to test mortality improvements from enemy ship awareness.

5. **When will GPU be available for #41 (RL training)?** The fundamental ceiling is RL. Every scripted improvement gives diminishing returns. Even basic LSTM trained for 1M steps would likely outperform our best scripted policy.
