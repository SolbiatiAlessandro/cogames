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

## 2026-04-13T00:01:00Z: starting to run baseline
