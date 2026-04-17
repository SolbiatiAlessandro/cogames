# Experiment Log: claude/amazing-meitner-pQoW5

## Issue: #40 — Mining throughput gap

We deposit ~500 elements at 10k steps. Top policy (dinky/Slytherin) deposits ~14,000.
Goal: Total element deposits >= 3,000 per 10k-step episode with 4 scripted miners.

## 2026-04-17T05:20: Autoresearch starting

**Plan**: Focus on mining throughput improvements. The issue identifies these key bottlenecks:
1. Miner pathing inefficiency (simple BFS cycle)
2. Element imbalance (miners cluster at same extractors)
3. Deposit trip overhead (return_load=40 means long round trips)
4. No extractor memory optimization
5. Hub distance (far extractors = longer round trips)

**Strategy**: Start with baseline measurement, then attack the biggest lever first.
Will run baseline at 500 steps and 1000 steps with 8 agents to measure current mining deposits.

## 2026-04-17T05:20: Baseline result (500 steps, 8 agents, seed 42)

- Per-agent reward: 0.31
- Total deposits: C=80, Ge=80, Si=40, O=80 → **280 total**
- Junctions aligned: 8, held ticks: 2627
- Hearts withdrawn: 8, gained/agent: 1.25
- Move failure rate: 24% (121.88/500 per agent)
- Deaths: 0.12 (nearly 0)

## 2026-04-17T05:25: Starting experiment loop

### Experiment 1: return_load=20 (from 40)

**Hypothesis**: Reducing return_load means miners make more frequent trips to hub with smaller loads.
**Result**: FAILED. Deposits dropped from 280 to 40 (only silicon). Scarce-element diversification doesn't trigger with smaller loads.

### Experiment 2: Diagnosis — miners are stuck, not dying

**Discovery**: Inventory tracing revealed miners are alive (inv:hp=100 throughout) but completely stuck:
- Agent 4: 40 carbon in `deposit_to_hub` from step 200 to step 3000 (2800 steps wasted)
- Agent 7: 40 germanium stuck the same way
- Agents 5, 6: stuck in `mine_until_full` with no progress

Root cause: `_scripted_skill_choice` only recognized "exited as stuck" but NOT "timed out after" as stuck. When deposit_to_hub timed out at 100 steps, the planner immediately re-selected deposit_to_hub instead of switching to explore.

### Experiment 3: Fix stuck cycle (commit d0c93b6)

Three fixes:
1. Bug fix: `_scripted_skill_choice` recognizes "timed out after" as stuck
2. Faster deposit timeout: 40 steps instead of 100 (stuck_threshold * 2)
3. Clear stale move_blocked_cells on deposit timeout

**Results (3000 steps, multi-seed):**

| Seed | Baseline | Fixed | Improvement |
|------|----------|-------|-------------|
| 42   | 1.02     | 1.58  | +55%        |
| 123  | —        | 1.54  | —           |
| 456  | —        | 1.64  | —           |

Deposits at 3000 steps: ~640 vs ~360 baseline (+78%)
At 10k steps: 641 deposits, reward 2.28. Deposits plateau at ~3000 steps because all agents die.

**Failed experiments in this batch:**
- Hub-proximal mining (prefer extractors near hub): regressed to 0.96 due to miner contention
- Hub-targeted explore after deposit timeout: regressed to 0.79
- Greedy walk fallback: no effect (navigation gap is BFS path-finding, not direction)

### Next: Agent mortality is the bottleneck

At 10k steps, deposits = 641 (same as 3k steps). All 8 agents die by step ~3000.
Key question: what kills agents when inv:hp stays at ~100?

