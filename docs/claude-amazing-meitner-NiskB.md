# Autoresearch: Issue #54 - A* Pathfinding / Navigation Efficiency (Session NiskB)

## Context
Continuing from EYYU7 session which found A* gives +3.4% offline but -8.9% online.
v52 (BFS-based) is current online best at rank #23 (36.35). Goal: online score > 38.0.

## 2026-04-30T09:00: autoresearch starting

My plan is to:
1. Run baseline (v52, current code) to confirm offline numbers
2. Investigate the offline-online gap - why does A* hurt online?
3. Focus on improvements that work for both offline AND online
4. Key areas: 10k step utilization (games are 10k online but agents idle after 3k),
   resource management (extend heart production), navigation efficiency without A*

## 2026-04-30T09:01: starting to run baseline

### Baseline Results (v52, BFS, 4A+4M)
| Seed | 3k steps | 10k steps |
|------|----------|-----------|
| 42   | 1028.09  | 3996.30   |
| 123  | 1096.04  | -         |
| 7    | 1179.58  | -         |
| **avg** | **1101.24** | - |

### Critical 10k step analysis (seed 42)
- heart.gained = 63 (SAME as 3k!)
- junction.aligned_by_agent = 52 (SAME as 3k!)
- All resources depleted by ~3k steps (oxygen.gained=900 at both 3k and 10k)
- For 70% of online game length (3k-10k), agents are IDLE
- Reward grows linearly with held-time: 3996.30 / 1028.09 = 3.89x

### Online tournament status (2026-04-30)
- v52: #25, score 36.18 (26 matches)
- #1: Paz-Bot-9000:v47, score 41.10
- Gap: 4.92 points (12%)
- ALL behavioral variants (v53-v58, A*) HURT online vs v52

### Offline-online gap analysis
Every behavioral change from v52 hurt online:
- v55 (defend): -1.45 online
- v56 (transit stuck fix): -2.87 online
- v57 (HP retreat): -4.95 online
- v58 (enemy priority): -4.96 online
- v54-astar: -3.23 online

Pattern: v52's BFS has a natural exploration-exploitation balance. Changes that optimize specific scenarios disrupt this balance.

### Strategy for this session
Focus on improvements that help the EARLY game (0-3k steps) to capture more junctions sooner. More junctions captured early = more junction-held reward over the full 10k game. Avoid behavioral changes that disrupt v52's balance.

## 2026-04-30T09:30: starting new experiment loop

### Experiment 1: Adaptive return_load (FAILED - dead code)
Attempted to modify MinerSkillImpl.step_with_state with adaptive return_load, but LLMMinerPolicyImpl.step_with_state OVERRIDES it. Change was never executed. Reverted.

### Experiment 2: Predicted miner station position (FAILED - negligible impact)
Added predicted station position (hub_center offset +4,+1) for gear_up. Only helps agent 0's first gear_up attempt (other agents share station via SharedMap). 3-seed avg: -0.7%. Reverted.

### Experiment 3: Approach side diversification + fast depletion detection
**Changes**:
1. **Approach side diversification** (`llm_skills.py:_gear_up`): Each miner approaches the station from a different side based on `agent_id % 4`. Previously all miners tried the same approach cell, blocking each other. Agent 0 was wasting 500+ steps (25 × 20 stale cycles) in gear_up loop.
2. **Fast mine depletion detection** (`llm_miner_policy.py:_maybe_finish_skill`): Reduced mine stale threshold from 20 to 8 steps for `mine_until_full`. When adjacent to an extractor with no cargo increase for 8 steps, mark it depleted immediately. Previously 22 stale exits × 20 steps = 440 wasted steps.

**Results (5-seed, 3k steps)**:
| Seed | Baseline | Experiment | Delta |
|------|----------|------------|-------|
| 42   | 1028.09  | 1121.22    | +9.1% |
| 123  | 1096.04  | 1073.88    | -2.0% |
| 7    | 1179.58  | 1204.06    | +2.1% |
| 99   | 1038.64  | 1146.96    | +10.4% |
| 256  | 1055.90  | 1046.90    | -0.9% |
| **avg** | **1079.65** | **1118.60** | **+3.6%** |

**Decision**: KEEP. +3.6% average improvement. Two seeds regress slightly but overall trend is positive.
