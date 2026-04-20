# Autoresearch Issue 44: Miner productivity plateau — deposits freeze at ~5k steps

Branch: `claude/amazing-meitner-pva5Z`

**Issue direction:** Miner deposits freeze at ~5000 steps because all extractors within the hub-weighted selection radius deplete. Miners lack long-range exploration to find fresh extractors. Need progressive exploration radius expansion and extractor-rotation logic.

**Success criteria (from issue):**
- Deposits sustained through 10k steps (no plateau visible in deposit-over-time curve)
- Junction alignment > 100 at 10k (currently 73, was 47 before Fb3vU fix)
- Per-agent reward > 2.0 at 10k steps (currently 1.77 best)

**Root causes identified in issue:**
1. Hub-weighted extractor selection (`miner_dist + hub_dist/2`) keeps miners close — good early, bad late
2. No extractor rotation: depleted → next nearest → also depleted → cascade
3. Exploration is passive: only when `scarce_element` has zero known extractors
4. Single hub bottleneck: all miners deposit at one hub

---

## 2026-04-20T10:30: autoresearch starting, my plan is to...

**Plan:**
1. Run 10k baseline with current code to establish the plateau quantitatively
2. Analyze extractor selection logic to understand exactly how miners pick targets
3. Implement progressive exploration radius — when known extractors deplete, expand search
4. Implement extractor freshness scoring — prefer unexploited extractors even if further
5. Test each change independently at 10k steps
6. Track deposits-over-time to see if plateau breaks

**Hypothesis:** The main bottleneck is that miners keep returning to depleted extractors because the selection heuristic (`miner_dist + hub_dist/2`) strongly prefers nearby extractors. Once the close ones deplete, miners waste steps walking to them and finding nothing. By tracking depletion and expanding search radius, we can sustain mining throughput.

---

## 2026-04-20T10:45: starting to run baseline

Running 10k baseline with 8 agents (4 aligners, 4 miners), scripted mode, seed 42.

## 2026-04-20T11:00: baseline result

- **Reward/agent: 2.314462**
- Total deposits: 681 (C=180 O=161 Ge=180 Si=160)
- Junction gained: 28, held: 13147
- Hearts withdrawn: 7

**Miner breakdown:**
| Agent | Mined | Fail% | Deaths | Max_stuck |
|-------|-------|-------|--------|-----------|
| 4     | 196   | 72%   | 8      | 3593      |
| 5     | 120   | 74%   | 1      | 1607      |
| 6     | 364   | 67%   | 3      | 3617      |
| 7     | 80    | 51%   | 1      | 50        |

**Key findings:**
- Miners are stuck for 3000+ steps (35% of episode!) — `max_steps_without_motion`
- Agent 4 dies 8 times — loses miner gear and cargo repeatedly
- Total miner output: 760 elements, only 1.9% efficiency
- Move failure rates 67-74% — massive congestion
- Agent 7 (51% fail, max_stuck=50) is 4x more productive than agent 4 (72% fail, max_stuck=3593)

**Root cause analysis:**
1. When extractors deplete, miners enter explore→stuck loops without expanding search radius
2. High death rate = cargo loss + time re-equipping miner gear
3. Congestion near hub/extractors causes 70%+ move failures
4. No mechanism to explore FAR from current known area

---

## 2026-04-20T11:10: starting new experiment loop

**Experiment 1: Progressive depleted-extractor tracking + far exploration**

Hypothesis: By tracking depleted extractors and preferring exploration AWAY from depleted areas, miners will find fresh extractors faster. Also adding exploration radius expansion — when local extractors are depleted, explore further from hub.

Changes:
1. Track `depleted_extractors` in SharedMap — when extractor is removed as stale, add to depleted set
2. When no known extractors AND depleted extractors exist, explore far from depleted cluster
3. Reduce miner stuck recovery time — force earlier exploration when mining stalls
4. Add miner anti-congestion: when near another miner, prefer different extractor direction

**Result: Changes were neutral (identical to baseline).** The depletion tracking barely triggered (only 1 extractor depleted per run). The real issue was move failure congestion, not extractor depletion.

---

## 2026-04-20T12:00: Root cause analysis — congestion deadlock bug

**Key discovery:** Miners are stuck for 3593+ consecutive steps because of a bug in the `move_blocked_cells` mechanism:
1. Move to cell X fails (another agent is there)
2. X added to `move_blocked_cells`
3. Next step: X is visible, no wall tag → "visually free" → X removed from `move_blocked_cells`
4. BFS routes through X again → fails again
5. Infinite loop for thousands of steps

The `move_blocked_cells` entries are cleared the very next step because other agents aren't visible as walls. BFS repeatedly routes through the same agent-occupied cell.

---

## 2026-04-20T12:30: Experiment 2 — Adaptive move cooldown

**Hypothesis:** Per-agent move cooldown with adaptive behavior. When a move fails, mark that cell as locally blocked for 6 steps so BFS finds alternative routes. But disable cooldown when the agent hasn't moved recently (structurally stuck, not temporarily blocked).

**Changes:**
1. `move_cooldown: dict[Coord, int]` per-agent — tracks cells where moves failed with TTL
2. BFS avoids cooldown cells (with fallback to no-cooldown BFS if path not found)
3. Cooldown only applied when `steps_since_move <= 12` (adaptive — disabled for structurally stuck agents)
4. Don't write to shared `move_blocked_cells` from miners (prevents degrading aligner BFS)
5. Cap cooldown at 16 entries to prevent pathological accumulation

**Results (3-seed average, +19.3% improvement):**

| Seed | Baseline | Experiment | Change |
|------|----------|------------|--------|
| 42   | 2.314    | 2.987      | +29.1% |
| 123  | 2.198    | 2.100      | -4.5%  |
| 7    | 2.330    | 3.060      | +31.3% |
| **Mean** | **2.281** | **2.716** | **+19.1%** |

**Seed 42 detailed metrics:**
- Junction.held: 19876 (baseline 13147, +51%)
- Hearts withdrawn: 9 (baseline 7, +29%)
- Total deposits: 1006 (baseline 681, +48%)
- Miner max_stuck: 50-51 steps (baseline 3593!, 70x reduction)
- Miner move success: 59-73% (baseline 28-49%, ~2x)
- Miner deaths: 64 (baseline 13, increased due to more active movement)

**Key insight:** The congestion deadlock fix benefits both miners AND aligners. Junction.held improved 51% because aligner BFS is no longer polluted by miner move failures (we stopped writing to shared `move_blocked_cells`).

**Cooldown sweep results (seed 42):**
- Cooldown=3: 1.93 (too short, BFS can't route around)
- Cooldown=5: 2.27
- Cooldown=6: 2.99 (BEST)
- Cooldown=7: 2.47
- Cooldown=8: 2.48

---

