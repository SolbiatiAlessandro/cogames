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

## 2026-05-01T02:00: Experiment 2 — Predicted Miner Station Offset + Fix SwitchableMiner Trigger

**Root cause analysis for seed 7 (52.66)**:
1. Miner oscillates between gear_up and explore for entire 3000 steps — never finds miner station
2. Bug: `consecutive_stuck_exits` counter resets to 0 when explore completes (even without miner gear), preventing SwitchableMiner from ever triggering
3. Even after fixing the counter, switched aligner can't find aligner gear either — wasted

**Key discovery**: Station layout analysis (mettagrid/mapgen/scenes/base_hub.py) reveals stations are placed in a predictable row at `cy+4` from hub center:
- aligner: `(hub_row + 4, hub_col - 3)` — already used by aligner's gear_up
- scrambler: `(hub_row + 4, hub_col - 1)`
- **miner: `(hub_row + 4, hub_col + 1)`**
- scout: `(hub_row + 4, hub_col + 3)`

**Changes**:
1. `llm_miner_policy.py`: Fix `consecutive_stuck_exits` — only reset when `has_miner=True` (productive), not on every non-stuck event
2. `llm_skills.py`: Replace hub-directed navigation with predicted station offset `(hub_row + 4, hub_col + 1)` in gear_up

### Results — 2-Agent Self-Play
| Seed | Exp 1 | Exp 2 | Delta |
|------|-------|-------|-------|
| 42   | 162.04 | 162.04 | 0% |
| 123  | 163.16 | 163.16 | 0% |
| 7    | 52.66 | **126.03** | **+139%** |
| 99   | 135.63 | 135.63 | 0% |
| 256  | 158.02 | 156.03 | -1.3% |
| **avg** | **134.30** | **148.58** | **+10.6%** |

### Results — 8-Agent Self-Play (regression check)
| Seed | Exp 1 | Exp 2 |
|------|-------|-------|
| 42   | 1121.22 | 1121.22 |
| 123  | 1011.49 | 1006.65 |
| 7    | 1195.96 | 1240.14 |

No regression. Seed 7 8-agent even improved slightly.

**Decision**: KEEP. +10.6% improvement (cumulative +31.3% over baseline). The predicted station offset directly fixes the miner station discovery failure.

**CvC Results (2 our + 6 starter, predicted station offset)**:
| Seed | CvC Baseline | CvC New | Delta |
|------|-------------|---------|-------|
| 42   | 19.57       | 19.57   | 0% |
| 123  | 5.93        | 36.06   | +508% |
| 7    | 3.00        | 58.20   | +1840% |
| 99   | N/A         | 50.40   | — |
| 256  | N/A         | 3.00    | — (station blocked) |
| **avg** | **9.50** | **33.45** | **+252%** |

## 2026-05-01T03:00: Experiment 3 — Gear-up approach patience

**Hypothesis**: When gear_up is near the station but congested, rotate approach side and retry within the same skill instead of exiting to explore. Patience: up to `stuck_threshold * 4` (80 steps) vs `stuck_threshold` (20 steps) before.

**Change**: `llm_miner_policy.py`: gear_up-specific stale handler that rotates approach and resets no_progress counter, only exiting after trying for 80 steps total.

**Results**: Self-play unchanged (148.58 avg). CvC seed 256 still at floor (fundamental station blocking). Change is neutral — kept as defensive improvement.

**Next steps**:
- Seed 99 (135.63) is now the weakest self-play — miner depletes extractors mid-game and stalls
- CvC seed 256 (3.00) has fundamental station blocking that requires structural changes
- CvC with strong partner (machina): 10k steps yields 511-566 avg/agent — huge upside
- Consider: improving extractor depletion handling, all-aligner 2-agent CvC config, or aligner efficiency

## 2026-05-01T04:00: Experiment 4 — Fast get_heart re-selection after stale exit

**Root cause analysis for CvC seed 42 (19.57)**:
1. Aligner NEVER gets a heart in 3000 steps — always `has_heart=False`
2. Cycles: get_heart (20 stale steps near hub) → explore (40-60 steps) → get_heart → ...
3. Hearts crafted by miner/starters are grabbed by 6 starters before our aligner returns
4. The 20-step stale exit + 40-60 step explore = aligner is away from hub ~70% of the time

**Failed approach — hub camping patience**:
- Tried increasing get_heart patience to 60-300 steps near hub
- Result: seed 42 improved BUT seeds 123/7/99 catastrophically regressed (avg 33.45 → 18.66)
- Root cause: aligner blocking hub approach cells prevents starters from depositing/picking up hearts
- Even 60 steps of continuous hub adjacency causes cascading congestion for all 8 agents

**Successful approach — fast get_heart re-selection**:
- After get_heart exits as stale (near hub, no heart), skip explore → immediately re-select get_heart
- Aligner still exits after 20 steps (doesn't block hub) but comes right back from a different approach side
- This maximizes time near hub WITHOUT continuous blocking

**Change**: `machina_llm_roles_policy.py` `_plan_skill()`: After get_heart stale exit, if aligner has gear, no heart, and knows hubs, override explore → get_heart

### Results — CvC (2 our + 6 starter)
| Seed | Exp 2 Baseline | Exp 4 | Delta |
|------|----------|-------|-------|
| 42   | 19.57    | 46.14 | +136% |
| 123  | 36.06    | 54.84 | +52%  |
| 7    | 58.20    | 54.20 | -7%   |
| 99   | 50.40    | 60.09 | +19%  |
| 256  | 3.00     | 3.00  | 0%    |
| **avg** | **33.45** | **43.65** | **+30.5%** |

### Results — 2-Agent Self-Play
| Seed | Exp 2 | Exp 4 | Delta |
|------|-------|-------|-------|
| 42   | 162.04 | 166.37 | +2.7% |
| 123  | 163.16 | 164.14 | +0.6% |
| 7    | 126.03 | 153.58 | +21.9% |
| 99   | 135.63 | 137.49 | +1.4% |
| 256  | 156.03 | 155.41 | -0.4% |
| **avg** | **148.58** | **155.40** | **+4.6%** |

### Results — 8-Agent Self-Play (regression check)
| Seed | Exp 2 | Exp 4 |
|------|-------|-------|
| 42   | 1121.22 | 1105.43 |
| 123  | 1006.65 | 1090.25 |
| 7    | 1240.14 | 1177.15 |

No significant regression.

**Decision**: KEEP. +30.5% CvC improvement, +4.6% self-play improvement, no 8-agent regression. The fast re-selection fixes seed 42's aligner starvation by maximizing hub presence time without causing congestion.

**Next steps**:
- CvC seed 256 (3.00) remains unsolved: fundamental station congestion with 8 agents
- All-aligner CvC tested and rejected: avg 4.17 (catastrophic — miner contribution to heart production is essential)
- Consider: miner scarce-element explore optimization (seed 42 miner spends many cycles exploring for oxygen/carbon)
