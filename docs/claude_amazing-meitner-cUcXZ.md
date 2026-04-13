# Autoresearch Issue 34: Heart Pipeline Throughput

Branch: `claude/amazing-meitner-cUcXZ`

**Issue direction:** Close the 5.4x heart pipeline throughput gap between us (10 hearts/agent) and dinky (56 hearts/agent). Our agents deposit enough resources for ~11 make_hearts but crafted hearts sit in the hub unclaimed. Need to increase heart.gained per agent from 10.4 to >=25 at 10k steps.

**Success criteria (from issue):**
- heart.gained per agent >= 25 at 10k steps (currently 10.4)
- aligned.junction.gained >= 100 (currently 56)
- Online score >= 5.0 average (currently 2.94)
- heart.withdrawn > 5 (proves make_heart hearts being consumed)

---

## 2026-04-13T00:00:00Z: autoresearch starting, my plan is to...

**Analysis of the problem:**
The heart pipeline has these stages: mine -> deposit -> make_heart -> get_heart -> align. The bottleneck analysis:

1. **Mining throughput**: dinky deposits 3244 carbon vs our 582. Our miners are ~5.5x slower.
2. **Make_heart efficiency**: With 582 carbon deposited and cost of 7 per element, we should get ~11 make_hearts. But heart.withdrawn=5 means we only use the initial 5 hub hearts.
3. **Get_heart timing**: After initial 5 hearts, the cooldown mechanism kicks in. Even though cooldown is short (2-8 steps), the retry-fail-cooldown cycle wastes time.

**Key insight from prior work (issue-16):**
- v13 (2A1M) showed make_heart working: 8-12 hearts in best runs
- The heart pipeline CAN work, but it's not consistent enough
- At 10k steps, there should be much more time for mining + make_heart cycles

**My plan:**
1. Run baseline at 1000 steps with best known config (cross_role, 4A+4M, scripted_miners=true)
2. Run baseline at 10k steps to measure the real gap
3. Experiment A: Reduce get_heart retry overhead - after deposit_to_hub completes, immediately attempt get_heart if agent is aligner (fast-path transition)
4. Experiment B: Add hub_hearts_available tracking (crafted - withdrawn) so agents know when new hearts are ready
5. Experiment C: Tune mining throughput - try lower return_load for faster deposit cycles, more miners
6. Experiment D: Reduce get_heart cooldown to minimum (1 step) to maximize heart pickup rate

---

## 2026-04-13T05:25:00Z: baseline results

**1000-step baseline** (4A+4M, scripted_miners, return_load=40):
- Reward: 0.40/agent
- Junctions gained: 6, held: 2985
- Hearts withdrawn: 8 (5 initial + 3 make_heart)
- Deposits: C=31, O=32, G=21, S=40

**10k-step baseline** (4A+4M, scripted_miners, return_load=40):
- Reward: 1.34/agent
- Junctions gained: 6, held: 3372 (clips: 1,184,541!)
- Hearts withdrawn: 10 (barely more than 1k!)
- Deposits: C=51, O=42, G=54, S=61
- **CRITICAL FINDING**: Deposits barely increase from 1k to 10k because miners die 1-5 times each and lose all resources

---

## 2026-04-13T05:30:00Z: experiments v1-v5 at 1000 steps

| Config | Reward | Junctions | Hearts | Carbon Deposited |
|--------|--------|-----------|--------|------------------|
| Baseline (rl=40) | 0.40 | 6 gained | 8 | 31 |
| v1 (reduced cooldown) | 0.40 | 5 gained | 8 | 40 |
| v2 (rl=20) | **0.50** | **7 gained** | 7 | **61** |
| v3 (2A+6M rl=20) | 0.14 | 5 gained | 6 | 74 |
| v4 (3A+5M rl=20) | 0.40 | 4 gained | 6 | 100 |
| v5 (no depleted + rl=20) | 0.48 | 8 gained | 8 | 71 |

**Key findings:**
1. **return_load=20 is key**: +25% reward from faster deposit cycles alone
2. **More miners ≠ better**: 2A+6M was terrible (0.14); 4A+4M is optimal at 1000 steps
3. **Disabling hub_depleted**: marginal improvement; the LLM prompt override wasn't the main bottleneck
4. **Mining throughput**: more deposits help but aligner efficiency is the binding constraint at 1000 steps

---

## 2026-04-13T06:00:00Z: v6 - HP-based emergency deposit (BREAKTHROUGH!)

**Hypothesis**: At 10k steps, miners die 1-5 times each, losing all carried resources. This erases mining progress. If miners detect low HP and immediately deposit, resources are saved.

**Implementation**: Added HP monitoring in step_with_state. When miner HP < 50% of max_seen and carrying resources, immediately switch to deposit_to_hub.

**v6 result at 1000 steps: 0.58/agent (+45% over baseline!)**
- 9 junctions gained (best yet!)
- 4799 junction held
- 0 miner deaths
- Carbon deposited: 101 (3.3x over baseline!)
- Combined effect of return_load=20 + no hub_depleted + emergency deposit

**Why this works**: Miners that would have died carrying 20 resources now deposit them first. Each deposit triggers make_heart if hub has enough resources (7 of each element). More successful deposits → more make_hearts → more hearts for aligners.

---

## 2026-04-13T07:10:00Z: v7 - persistent aligner retry + hub heart theft prevention (BREAKTHROUGH #2!)

**Root cause discovery from v6 10k partial run (step 1144):**
At 10k steps, v6 had `team_aligners: 1, team_miners: 7`. Only 1 of 4 designated aligners kept aligner gear! The other 3 got contaminated (walked through scrambler/scout stations) → failed to re-gear as aligner within 200 steps → fell back to miner gear. This was the REAL heart pipeline bottleneck.

**Two fixes:**
1. **Persistent aligner retry**: Designated aligners NEVER fall back to miner gear. After contamination, always retry gear_up_aligner regardless of failure count.
2. **Hub heart theft prevention**: Added `isNot(actorHas({"miner": 1}))` filter to get_heart, get_last_heart, get_and_make_heart handlers. Miners were stealing hearts when depositing (all matching handlers fire on hub use).

**v7 result at 1000 steps: 0.84/agent (+45% over v6, +110% over baseline!)**
- 13 junctions gained (vs 9 in v6, vs 6 in baseline)
- 7425 junction held (vs 4799 in v6)
- Hearts withdrawn: 10 (vs 8 in v6)
- team_aligners: 3, team_miners: 3 (vs 1:7 in v6 10k!)
- 0 miner heart theft (hub filter working)
- Agent 3 aligned 8 junctions, Agent 0 aligned 5
- Agent 2 stuck in get_heart→stale→unstuck cycle (navigation issue)

**Remaining issue**: Agent 2 spent entire episode failing to reach hub. "get_heart exited as stale after 20 steps" repeatedly. This is a navigation bottleneck, not a heart availability issue.

**Running v7 at 10k steps to measure full improvement.**
