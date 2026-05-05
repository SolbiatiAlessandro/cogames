# Director Notes
_Written: 2026-05-05 (Session 27 — offline-to-online)_

## Offline observations

- Main branch contains hCVEi merge + aSOVe merge + NiskB changes on top of v52
- The hCVEi branch added: hub approach rotation, station blacklisting, switchable miner, extended explore, fast depletion breaker, drought reset, defend timeout halving
- TSV results showed these as "no regression" or "+0.5%" in offline eval — but they REGRESSED 10% online
- This confirms the offline→online gap: short offline evals (80-1000 steps) don't predict 10,000-step online performance

## Online observations

### Leaderboard (beta-cvc, 565 entries)
- #1: slanky:v171 (41.28, 20 matches) — new leader
- #2: Paz-Bot-9000:v47 (41.10, 21 matches) — former leader
- #3: Gryffindor:v11 (40.82, 27 matches)
- #33: **lessandro-scripted-v52:v1 (36.11, 50 matches)** — OUR BEST, stable
- #48: lessandro-scripted-v59:v1 (34.91, 26 matches) — hCVEi code, REGRESSED

### v59 performance (27 matches, avg=31.15)
- Range: 2.6 (with anoop.chen) to 48.3 (best)
- vs v52 (50 matches, avg=34.61): 10% regression confirmed
- All 12 bekkenze v9-v11 matches still FAILED (crashed)

### Replay analysis: v59 high match (44.4) vs v52 high match (52.4)
- v52: 241 junctions gained, 524,300 held, best agent 9,653/10,000 steps
- v59: 103 junctions gained, 444,091 held, best agent 5,500/10,000 steps
- Both: zero vibe transitions (expected), zero deaths
- v52 had 6 Slanky partner agents (the #1 policy) — explains the high score
- v59 had 2 ron.calib.top_a partner agents + 6 of ours

### Key behavioral difference
- v52 agent_7: 9,653 steps, 9,648 moves, 5 noops — nearly 100% utilization
- v59 best agent: 5,500 steps, 5,241 moves, 259 noops — 55% utilization
- The hCVEi changes are causing agents to get stuck in loops or die earlier

## Offline→Online gap analysis

1. **Offline best**: v52 code (commit `0c947d7`). The hCVEi additions showed "no regression" offline but -10% online.
2. **Online best**: v52:v1 at #33 (36.11, 50 matches, stable)
3. **Gap is NOT closing**: v59 (latest code) regressed. No improvement since v52 (submitted ~2026-04-22).
4. **Root cause of gap**:
   - The hCVEi changes add complexity that wastes steps on non-productive behaviors (blacklisting, extended exploring, switching roles)
   - In 10,000-step online matches, these "safety nets" consume time that could be spent capturing junctions
   - Offline evals at 80-1000 steps can't detect this because the negative effects only manifest at scale
5. **Bottleneck**: The code on main is WORSE than what's submitted. **Main needs revert to v52 before any new work.**

## Current bottleneck

**Code regression on main.** The #1 priority is reverting the policy files to v52 (issue #63). Until that happens, all new experiments build on a bad baseline and their results are meaningless for online improvement.

After revert, the bottleneck returns to: per-agent junction capture rate and exploration coverage (#62).

## Issues updated this session

- **#63**: CREATED (priority:1) — Revert main to v52 policy code. Blocking all other work.
- **#62**: COMMENTED — Added v59 regression evidence, v52 vs v59 replay comparison
- **#50**: No change (priority:1, after revert)
- **#61, #56, #57**: No change (priority:3, mortality wrong)

## Branches NOT merged (and why)

- All branches should build on reverted v52 code, not current main
- No new promising branches found this session
- New branches (pr/issue-12-gear-picking-fix, pr/cogames-watch-replay-skill, revert/pr-13-gear-up-navigation) are maintenance/tooling, not policy improvements

## Open questions for next director

1. **Should we do the revert ourselves or wait for the user?** The revert is `git checkout 0c947d7 -- src/cogames/policy/{machina_llm_roles_policy,llm_miner_policy,llm_skills}.py`. It's safe but touches core files.
2. **After revert, should we re-submit as a new policy?** To confirm the reverted code matches v52's performance, we should submit it under a new name and verify ~36 score.
3. **Why does v52 agent_7 survive 9,653 steps but v59 agents max at 5,500?** Is this partner-dependent (Slanky is a much better partner) or is the hCVEi code causing early death? Need more replays with comparable partners.
4. **Can we identify experiments from #62 that DON'T add the type of complexity that hCVEi added?** Experiment A (quadrant assignment) and Experiment D (enemy junction recapture) are simple routing changes, not complex state machines. These are safest to try first.
5. **The variance problem**: v52 ranges from 4.9 to 53.1 (10x). Can we reduce the floor without hurting the ceiling? The floor seems partner-dependent (bad partners = low score regardless).
6. **beta-teams-tiny-fixed season**: Still only 10 entries. Should submit v52 there for free placement.
7. **Why did v52's rank drop from #29 to #33?** More entries (493→565), not score change. Competition is getting stiffer — time is a factor.
