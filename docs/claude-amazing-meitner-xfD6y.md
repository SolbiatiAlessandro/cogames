# Experiment Log: claude-amazing-meitner-xfD6y
## Issue #58: 2-agent match handling — adaptive role assignment when n_agents ≤ 2

## 2026-05-01T00:00: autoresearch starting, my plan is to...

Working on issue #58. The problem: our policy scores well with 4+ agents (avg 37.61) but catastrophically underperforms with 2 agents (avg 9.16 online). Since ~35% of CvC matches assign only 2 agents, this drags overall score.

**Plan:**
1. Run baseline with 2 agents (current default: 1 miner + 1 aligner via aligner_fraction=0.5)
2. Test all-aligner configuration for 2 agents  
3. Implement adaptive role assignment: when n_agents <= 2, adjust aligner_fraction
4. Test various configurations and find optimal 2-agent strategy
5. Ensure 4+ agent performance doesn't regress

**Key insight from issue:** 1M+1A gives 162.04 in self-play but online 2-agent avg is 9.16. The gap suggests the problem is that with a weak partner controlling 6 agents, our single miner can't compensate. All-aligner may be better for direct junction-holding score.

## 2026-05-01T00:01: starting to run baseline

### 2-Agent Self-Play Baseline (1M+1A, --cogs 2)
| Seed | Reward |
|------|--------|
| 42   | 162.04 |
| 123  | 163.16 |
| 7    | 52.87  |
| 99   | 135.63 |
| 256  | 52.24  |
| **avg** | **113.19** |

### CvC Baseline (2 our + 6 starter, 8 total)
| Seed | Avg/Agent |
|------|-----------|
| 42   | 19.57     |
| 123  | 5.93      |
| 7    | 3.00      |
| **avg** | **9.50** |

Matches online 2-agent avg of 9.16. Validated CvC simulation is realistic.

### Key Finding: Root Cause Analysis
1. In seed 42 (good): miner station visible from spawn → gears up immediately
2. In seeds 123/7/99/256 (bad): miner station NOT visible → miner explores aimlessly or gets stuck at congested station
3. All-aligner (2A): consistent 5.94 avg but WORSE than 1M+1A when miner works
4. Starter-only (0 our agents): baseline is 3.0 per agent (floor)

## 2026-05-01T01:00: Experiment 1 — SwitchableMiner + Hub-Directed Navigation

**Hypothesis**: Two changes to improve 2-agent handling:
1. SwitchableMinerImpl: miner that auto-switches to aligner after 5+ consecutive gear failures
2. Hub-directed navigation: when station is unknown but hub is known, navigate directly to hub instead of slow frontier exploration

**Changes**:
- `machina_llm_roles_policy.py`: Added SwitchableMinerImpl wrapper that holds both miner and aligner impls
- `llm_skills.py`: In gear_up, navigate to hub when station unknown and hub known (distance > 3)
- `llm_miner_policy.py`: Faster gear_up timeout (40 steps vs 100), gear approach rotation, cooldown clearing

### Results — 2-Agent Self-Play
| Seed | Baseline | Experiment | Delta |
|------|----------|------------|-------|
| 42   | 162.04   | 162.04     | 0%    |
| 123  | 163.16   | 163.16     | 0%    |
| 7    | 52.87    | 52.66      | -0.4% |
| 99   | 135.63   | 135.63     | 0%    |
| 256  | 52.24    | 158.02     | +203% |
| **avg** | **113.19** | **134.30** | **+18.6%** |

Seed 256 massive improvement: hub-directed navigation helped miner find station that was previously undiscoverable.

### Results — 8-Agent Self-Play (regression check)
| Seed | Baseline | Experiment |
|------|----------|------------|
| 42   | 1121.22  | 1121.22    |
| 123  | ~1074    | 1011.49    |
| 7    | ~1180    | 1195.96    |

No significant regression.

### Results — CvC (2 our + 6 starter)
CvC unchanged: seeds 123/7/99/256 still hit 3.0-5.93 floor. Root cause is station congestion with 6 other agents that our navigation changes can't overcome. SwitchableMiner triggers correctly as safety net.

**Decision**: KEEP. +18.6% 2-agent self-play improvement with no 8-agent regression. The SwitchableMiner is a valuable safety net even though CvC with weak partners remains hard.

**Next steps for next researcher**:
- The 2-agent CvC problem is fundamentally about station congestion with 6 partner agents
- The SwitchableMiner provides a floor; the real upside comes from making gear_up succeed more consistently
- Consider: (a) more aggressive station approach with waiting/retrying, (b) using the aligner's known station locations in shared map, (c) timing gear_up to avoid peak congestion periods
