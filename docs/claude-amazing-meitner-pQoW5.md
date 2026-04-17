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

**Hypothesis**: Reducing return_load means miners make more frequent trips to hub with smaller loads. This reduces time spent walking to/from hub per deposit cycle. Issue #40 suggested this — shorter trips = more mining time.

