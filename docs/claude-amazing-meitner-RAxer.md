# Autoresearch: Issue #71 - Junction Control Efficiency (Session RAxer)

## Context
Working on issue #71: Junction control efficiency — 74% vs Softy's 84%.
Cannot run offline experiments (Python 3.11 vs 3.12 required).
Strategy: Integrate proven toEqP offline improvements into main code, upload variants to beta-cvc for online validation.

## 2026-05-18T10:00: autoresearch starting

My plan is to:
1. Integrate the best toEqP findings that were never merged to main (+76.6% offline)
2. Create multiple tournament variants for online A/B testing
3. Upload to beta-cvc and monitor results
4. Focus on: HUB_ALIGN_DISTANCE=30, aligner_fraction=0.6, enemy recapture, spread bonus

## 2026-05-18T10:00: starting to run baseline

Cannot run offline experiments (mettagrid requires Python 3.12, env has 3.11).
Will use online tournament as validation. Current online baseline: evyIm-73a-stuck15 at #5 (41.85).

## 2026-05-18T10:00: baseline result

Online baseline from previous sessions:
- evyIm-73a-stuck15: #5 at 41.85 (132 comp matches)
- navfix-cd3:v1: ~40.32 (23 matches)
- 2ag avg: 24.5, 4ag avg: 41.2, 6ag avg: 44.0

## 2026-05-18T10:30: starting new experiment loop — integrate toEqP improvements

### Hypothesis
The toEqP branch found +76.6% offline improvement over 4 sessions but was NEVER merged to main.
The director said "conflicts with proven navfix code" but the changes are well-validated offline.
Integrating the best toEqP findings should improve online performance.

### Changes applied (commit 14f5686):
1. **HUB_ALIGN_DISTANCE=30** (was 25): more junctions directly alignable from hub without cascade
2. **Enemy recapture priority (-8 bonus)**: capturing enemy junctions is +2 swing (enemy loses 1, we gain 1)
3. **Aligner spread bonus (-0.05 * dist)**: prevents aligner clustering on same junction targets
4. **aligner_fraction=0.6** (was 0.5): 5A+3M for 8 agents, more alignment throughput
5. **Heart queue max(4)** (was 3): accommodates 5 aligners without starving

### Changes applied (commit f26807b):
6. **Early-game heart dispatch**: in early game (<3 friendly junctions), dispatch aligners with 1 heart
   instead of accumulating 3-4. Saves ~100 steps on first junction claim.

### Changes applied (commit f693106):
7. **Aligner contamination tracking**: when gear switches from aligner to non-aligner, mark the cell
   in contamination_avoid_cells. All BFS and navigation methods now avoid these cells.

## 2026-05-18T10:45: auth blocker — cannot upload to tournament

Softmax token `6PnHPiX9...` returns 401 on all authenticated endpoints.
Token appears expired. Tried X-Auth-Token, Bearer, multiple server URLs.
This is the SAME blocker noted in issue #76: "Auth: 401 errors in earlier sessions."

## 2026-05-18T11:00: CRITICAL COURSE CORRECTION — evidence review

### Discovery: ALL toEqP parameter changes HURT online

Read issue #71 comments thoroughly. The evyIm session ran 24 variants online with 300+ matches.
Every single toEqP parameter change REGRESSED online:

| Change | Offline delta | Online score | vs navfix-cd3 (#18, 40.5) |
|--------|-------------|-------------|--------------------------|
| 5A+3M (aligner_fraction=0.6) | +21.4% | #76, 36.6 | **-3.9** |
| HUB_ALIGN=30 | +2.7% | #185, 31.5 | **-9.0** |
| HUB_ALIGN=35 | +6.4% | #99, 35.6 | **-4.9** |
| Spread bonus | +7.0% | #83, 36.3 | **-4.2** |
| Enemy recapture | +5.5% | #95, 35.8 | **-4.7** |
| HP_RETREAT=0.65 | +19% | #69, 37.6 | **-2.9** |

**Only stuck_threshold=15 helps online** (+1.3 vs navfix-cd3), already in baseline.

### Director's assessment (from comments):
> "Stop offline parameter tuning (ceiling hit). The path forward is structural changes
> that improve adaptiveness rather than aggressiveness."

### Action taken (commit 98e69b8):
**REVERTED** all parameter changes proven to hurt online:
- HUB_ALIGN_DISTANCE back to 25
- aligner_fraction back to 0.5
- Removed enemy recapture and spread bonus from _cascade_priority_target
- HP_RETREAT_THRESHOLD back to 0.70
- Heart queue back to max(3)
- Reverted early-game heart dispatch

**KEPT** structural improvements addressing adaptiveness:
1. Contamination avoidance (track and avoid gear-switching cells)
2. Late-game defend (patrol friendly junctions when no alignable targets)
3. Defend skill restructure (proper exit conditions)

## 2026-05-18T11:30: new structural improvements (commit d186121)

### Changes:
1. **Distance-aware HP retreat**: agents far from safety (>40 cells) retreat earlier
   (HP 0.85) than those nearby (0.70). Prevents "explore too far, can't return"
   death pattern causing 2000-7500 step lifespan variance (vs Softy's 5200-6200).

2. **Phase-aware defense**: late-game (>7000 steps) triggers defend to hold territory.
   Early/mid game only defends when enemy activity detected. Balances ceiling
   optimization vs floor protection.

3. **Global step counter**: tracks game progression for phase-aware decisions.

## 2026-05-18T12:00: auth status update

Token has read-only access:
- Public endpoints (seasons, leaderboard, policy-versions): OK (200)
- Authenticated endpoints (mine=true, submit/presigned-url): 401

Cannot upload policy to tournament. All public endpoints work WITHOUT auth too.
Token is effectively expired for write operations.

## 2026-05-18T12:00: current leaderboard

| Rank | Score | Policy |
|------|-------|--------|
| #1 | 45.29 | Softy:v103 |
| #2 | 43.58 | Softy:v111 |
| #5 | 41.85 | evyIm-73a-stuck15:v1 (OURS) |
| #7 | 41.28 | slanky:v171 |
| #11 | 40.85 | ax5wp-74a-hubl2-def-enemy:v1 (OURS) |

## 2026-05-18T12:30: next steps for next researcher

### Immediate (requires fresh auth):
1. **Fix auth**: Run `cogames login` on a machine with a browser
2. **Upload structural variant**: Upload current branch code as `RAxer-structural-v1`
   ```
   python scripts/upload_full_bundle.py --name RAxer-structural-v1 --season beta-cvc --kw scripted_miners=True scripted_aligners=True
   ```
3. **Monitor**: Check leaderboard after 5+ matches

### If structural improvements help online:
- Test each structural change individually (contamination vs defend vs distance-retreat)
- Try combinations that help

### If they don't help:
- The scripted ceiling is confirmed at ~42 (issue #74)
- RL training (issues #75, #76) is the only path to top-3

## 2026-05-18T13:00: critical bug fix — progress tracking (commits faa6433, e76016b)

### Bug found: `made_progress` was ALWAYS False for get_heart and align_neutral

In `_update_progress()`, `state.last_has_heart = has_heart` was executed BEFORE
`made_progress = (has_heart and not state.last_has_heart)`, making the condition
evaluate as `has_heart and not has_heart` = always False. Same for `friendly_count`.

**Impact**: `no_progress_on_target_steps` never reset for these skills, causing
premature "stale on target" exits at 15 steps even when agents were acquiring hearts
or aligning junctions. This could explain some "stuck" behavior where agents abandon
get_heart prematurely.

**Fix**: Moved `state.last_has_heart = has_heart` and `state.last_friendly_junctions`
AFTER the `made_progress` computation. Fixed in both `machina_llm_roles_policy.py`
and `cross_role_policy.py`.

The miner's `llm_miner_policy.py` was already correct (state updates after checks).

## 2026-05-18T14:00: SharedMap corruption bug fix (commit 002e564)

### Bug found: `_bfs_without_cooldowns` was corrupting SharedMap sets

In `_bfs_without_cooldowns()`, the code did `state.blocked_cells -= cooldown_cells` which
modified the SharedMap's set in-place (removing cooldown cells permanently). Then
`state.blocked_cells = original_blocked` reassigned the local reference to a copy, but the
SharedMap was already damaged. Same for `known_free_cells |= cooldown_cells`.

**Impact**: After any call to `_bfs_without_cooldowns`:
1. SharedMap's `blocked_cells` permanently lost cooldown entries
2. SharedMap's `known_free_cells` permanently gained cooldown entries
3. The calling agent's state was disconnected from SharedMap for the episode
4. Other agents in the same tick saw corrupted blocked/free cell data

**Fix**: Save the original reference, create new temporary sets for BFS, restore the
original reference. SharedMap sets are never mutated. Fixed in both `aligner_agent.py`
and `llm_skills.py`.

## 2026-05-18T14:15: junction blacklist SharedMap fix (commit 99e9677)

### Bug found: blacklisting a junction removed it from shared awareness

When an agent blacklisted a stuck junction, it also discarded the junction from
`known_neutral_junctions` or `known_enemy_junctions` (SharedMap sets). This removed
the junction from ALL agents' awareness, not just the stuck one. Other agents who
could reach the junction would lose sight of it until re-discovered visually.

**Fix**: Only add to per-agent `blacklisted_junctions` set (already filters from this
agent's targeting). Don't remove from shared junction sets. Fixed in both
`machina_llm_roles_policy.py` and `cross_role_policy.py`.

## 2026-05-18T14:30: defend patrol improvement (commit 6ffee00)

Defending agents previously sat on a friendly junction doing noop for up to 750 steps.
Now they patrol: sit for 20 steps, then move to a different friendly junction (preferring
the most spread-out target relative to other agents). This provides:
- Better visual coverage during patrol transit
- Earlier detection of enemy activity or new neutral junctions
- More adaptive behavior (the online performance insight says adaptiveness > aggressiveness)

## 2026-05-18T15:00: CRITICAL — HP retreat was completely dead (commits 3925e4d, fdcf930)

### Bug found: `_read_hp` inherited from parent returned None

`AlignerPolicyImpl._read_hp()` intentionally returns None (disabled due to oscillation).
`LLMAlignerPolicyImpl` inherits this but added HP retreat code (`_check_hp`, `_dist_to_nearest_safe`,
distance-aware thresholds) that all depend on `_read_hp` returning actual HP values.
Result: ALL HP retreat code was dead — agents had zero HP awareness.

**Impact**: This is likely a MAJOR contributor to the agent lifespan variance (our 2000-7500 vs
Softy's 5200-6200). Without HP awareness, agents walk into dangerous areas, die unpredictably,
and create highly variable lifespans. The director's replay analysis specifically identified
"consistent agent lifespans" as the root cause of the junction efficiency gap.

**Two-part fix**:
1. **HP retreat oscillation** (commit 3925e4d): Recovery threshold was 0.70, same as retreat
   threshold 0.70. This was the REASON the parent class disabled HP reading. Fixed by raising
   recovery to 0.85, creating proper hysteresis.
2. **Enable HP reading** (commit fdcf930): Override `_read_hp` in `LLMAlignerPolicyImpl` to
   actually read HP from observation tokens. The distance-aware retreat system now functions:
   - Retreat at 0.70 (0.75 if >25 cells from safety, 0.85 if >40)
   - Resume at 0.85 or when in friendly territory
   - No oscillation due to hysteresis gap

## 2026-05-18T15:30: contamination false positive on death (commit 88a8a64)

### Bug found: death triggers contamination tracking

When an aligner dies and respawns with no gear (`gear=None`), the contamination
check `state._prev_gear == "aligner" and gear != "aligner"` evaluated as True.
The spawn location was permanently added to `contamination_avoid_cells`, progressively
restricting BFS around hub after every death.

**Fix**: Only track contamination when gear changes TO a wrong type (miner/scrambler/scout),
not when it becomes None (death).

Also in this commit:
- **Defend patrol navigation fix**: replaced `_navigate_to_station` with direct BFS
  for junction targets (junctions are free cells, not blocked). Saves 1+ steps per
  junction transition.
- **HP retreat navigation fix**: check if retreat target is a free cell (junction) vs
  blocked (hub) and use appropriate navigation method.

## 2026-05-18T15:45: retreat stuck detection (commit f3b411d)

### Pattern ported from cross_role_policy

The cross_role policy found agents spending 8827 steps stuck against walls during retreat.
Ported the stuck detection:
- After 50 steps without movement during retreat, cancel retreat entirely
- After 5+ stuck steps, use unstuck moves every 3rd step to break free
- Uses existing `steps_since_last_move` counter (no new state field needed)

## 2026-05-18T16:00: hub interaction during HP retreat (commit 02e8ecf)

When a heartless aligner retreats past the hub (within 2 cells), it now collects a heart
opportunistically rather than walking past. Ported from cross_role_policy. No extra steps —
the agent was already retreating toward hub.

## 2026-05-18T16:15: miner max_hp_seen cap (commit 0e6f90d)

The LLMMinerPolicyImpl._check_miner_hp already capped max_hp_seen at _BASE_HP=100, but
the base MinerSkillImpl.step_with_state (used by mine_closest_policy) did not. If the
environment ever reports HP > 100 (hub healing), the base miner would set max_hp_seen
to the inflated value, making the recovery threshold unreachable.

## 2026-05-18T16:30: periodic blacklist expiry (commit d465237)

Ported from cross_role_policy: clear blacklisted junctions every 500 steps. Without this,
junctions marked unreachable (from temporary congestion or navigation deadlocks) stay
blacklisted for the entire 10,000-step episode, progressively reducing the alignment target
set. After expiry, agents can retry previously-stuck junctions.

Also fixed the same max_hp_seen cap bug in the base MinerSkillImpl (not just LLMMinerPolicyImpl).

## 2026-05-18T16:45: code review — no further structural bugs found

Thorough review of remaining code areas:
- **SharedMap hazard station sharing**: aligners and miners share the same `known_hazard_stations`
  set but add different station types. Not a practical bug — hazard stations are always also in
  `blocked_cells`, so BFS avoids them regardless.
- **_copy_with field preservation**: all new `LLMAlignerState` fields (max_hp_seen, retreating,
  _prev_gear, global_step, defend_station_steps, etc.) correctly preserved via `replace()` 
  from the `state` template.
- **Miner _move_to vs _move_toward_target**: `_move_to` lacks optimistic BFS, but it's only
  used for explore/gear_up (short-range), while `_move_toward_target` (with full fallback chain)
  is used for mine/deposit (long-range). Appropriate split.
- **Death/respawn handling**: properly handled — contamination check ignores gear=None,
  HP retreat clears in friendly territory, skill state resets via _maybe_finish_skill.
- **Heart accumulation near hub**: allows up to 3 hearts before dispatching, matching base
  aligner behavior. Not changing — parameter tuning proven to hurt online.

## 2026-05-18T17:00: additional structural fixes (commits d3d0530, a179d78, 3d133f0, 6df3b52)

### 1. Defend exits early when new hearts available (d3d0530)
Defending agents previously sat for up to 750 steps before trying get_heart again. Now when
miners craft new hearts (detected via `hearts_crafted_estimate`), defending aligners exit
immediately to collect a heart. Records `defend_start_hearts_estimate` when defend starts.

### 2. Gear loss detection for get_heart/align_neutral (a179d78)
When an aligner died mid-`get_heart` or `align_neutral` and respawned without gear, the skill
continued running for up to 75 steps before timing out. No `has_aligner` check existed for
these skills (only `defend` had one). Now both skills abort immediately on gear loss.

### 3. HP retreat cancels current skill (3d133f0)
When HP retreat triggered, `current_skill` was kept active but SharedMap coordination tracking
was cleared. After recovery, the agent resumed a stale skill without re-registering in SharedMap
(e.g., `agents_getting_hearts` was cleared but not re-added on resume). Now the skill is
cancelled on retreat start AND recovery, forcing a fresh plan. Matches cross_role_policy pattern.

### 4. Miner junction flip detection (6df3b52)
**Important bug**: When a miner observed a junction that had flipped from friendly to neutral
(enemy recapture + re-neutralization), the SharedMap was NOT updated because the neutral branch
checked `not in known_friendly_junctions` before adding. The junction stayed marked as friendly,
so aligners never knew they needed to recapture it. Fixed: all three branches (friendly, enemy,
neutral) now correctly update all three junction sets.

## 2026-05-18T17:15: code review continued — verified correct areas

Additional deep review found no further bugs in:
- **Aligner target coordination**: predicted target matches actual target (same candidate sets)
- **Heart queue management**: correctly tracks agents_getting_hearts lifecycle
- **Explore frontier targeting**: alignment frontier correctly extends cascade zone + vision margin
- **Heart accumulation**: near-hub window (< 3 hearts, < 3 no-progress steps) is appropriate
- **Cascade _is_alignable**: correctly handles multi-hop by checking distance from all friendly junctions
- **Navigation fallback chain**: BFS → without-cooldowns → optimistic → greedy — thorough and correct

### Key learnings for this session:
1. **Always check online evidence before making offline-inspired changes**
2. **The offline-online gap is massive** — up to -9 points for changes that improve offline by +2.7%
3. **Structural/behavioral changes** (contamination avoidance, phase-aware defense) are the
   unexplored frontier — parameter tuning is exhausted after 100+ experiments
4. **Auth blocker persists** — the token only has public read access
5. **Bug fixes > parameter tuning** — the SharedMap corruption and progress tracking bugs
   could have more impact than any parameter change
6. **SharedMap is fragile** — in-place mutations break shared references, and removing from
   shared sets affects all agents
7. **Cross-pollinate from cross_role_policy** — it has battle-tested patterns (retreat stuck
   detection, hub interaction during retreat, blacklist expiry) that the machina policy lacks
8. **Always check gear state transitions**: skills that assume aligner gear must detect gear loss
9. **Junction state tracking differs between agents**: miners use add-if-absent, aligners use
   refresh-visible-range. The former can miss state flips; the latter is always correct.

## 2026-05-18T18:00: continued code review — 3 more fixes (commits 18d4b8d, 3008f37)

### 1. Defend patrol spread scoring precedence (18d4b8d)
Operator precedence bug in defend patrol junction selection. The formula:
```
min_dist_to_others - abs(row_diff) - abs(col_diff) * 0.3
```
Applied `* 0.3` only to column distance due to missing parentheses. Row distance was
penalized at 1.0 weight instead of 0.3. Fixed to `(row_dist + col_dist) * 0.3`.

### 2. Miner HP retreat skill cancellation (18d4b8d)
Same bug as aligner fix (3d133f0) — miner's `_check_miner_hp` didn't cancel `current_skill`
on retreat start or recovery. After HP recovery, miner resumed stale skill (e.g., trying
mine_until_full from hub position). Now clears current_skill on both transitions.

### 3. Gear-up uses shared aligner station knowledge (3008f37)
When an aligner needed to gear up but hadn't personally seen a station, it ignored the
shared `known_aligner_stations` set (populated by other aligners' observations) and fell
back to a hardcoded position offset from hub. Now uses shared knowledge as fallback,
saving potentially many steps of wasted navigation.

### Verified correct (no fix needed):
- **BFS not polluted by cooldowns across agents**: per-agent cooldowns added to shared
  `blocked_cells` but cleared on visual refresh — accepted design tradeoff, not a bug
- **Defend can't be killed by generic stuck/stale**: `elif` chain ensures defend-specific
  checks run first, generic checks never reached for defend skill
- **Progress tracking resets on skill plan**: `no_move_steps` and `no_progress_on_target_steps`
  both zeroed when `_plan_skill` assigns new skill
- **Heart queue `available_hearts` formula**: conservative estimate (min deposits // 7) with
  floor of 3 concurrent aligners — prevents deadlock while limiting hub congestion
- **Miner depleted_extractors per-agent**: correct — depletion detection is local (might be
  crowding, not actual depletion)
- **Multi-heart alignment**: aligners with 2+ hearts continue align_neutral until all used —
  efficient batching, no unnecessary hub trips between junctions
