# Director Notes
_Written: 2026-05-21 (Session 37, offline-to-online)_

## Offline observations

### Critical bug fix: neutral-only alignment (+129.5%)
Branch v1EZZ (`f2b6ca5`) discovered that `_align_neutral()` and `_known_alignable_junctions()` included `known_enemy_junctions` in the alignable target set. Enemy junctions have `team:clips` tag — the game requires `isNot(hasTagPrefix("team:"))` for alignment. Aligners were navigating to enemy junctions, failing to align, timing out, and wasting hearts+steps.

**Fix**: Remove `| state.known_enemy_junctions` from 3 locations in `aligner_agent.py` and `machina_llm_roles_policy.py`. Applied to main.

**Result**: 6-seed avg 8.63 vs 3.76 baseline (+129.5%) on 8-agent, 3000-step, competition map.

### Other branch observations
- **lBgBD**: HP retreat for aligners (+4.1% on Machina1 10K). Clean 1-commit change. NOT merged — improvement is modest and may interact with neutral-only fix.
- **v1EZZ full branch**: Also includes scrambler role, depleted extractor sharing, shared map corruption fix. Too many changes to merge safely. Only cherry-picked the neutral-only fix.
- **dz2Gf**: 55+ experiments, confirmed +3.9% ceiling from BFS fixes. Already included in v1EZZ.

## Online observations

### Leaderboard (beta-cvc, 949 entries)
- **#1**: `all_role_policy_v1shapeterr4_auto_model035000:v1` — 49.40 (NEW, safaalver-softmax)
- **#5**: `Softy:v103` — 45.29 (was #1)
- **#15**: `evyIm-73a-stuck15:v1` — 41.85 (was #5, OUR BEST)
- New competitor `safaalver-softmax` uploaded 10+ RL checkpoints (model steps 2500-35000), taking 10 of top 14 spots

### Match replay analysis (3 matches)

**Match 1: our policy + top RL (score 52.5)**
- 6 RL agents + 2 ours (lessandro-navfix-cd3)
- RL agents: 4 die early (1300-1650 steps / 13-16%), 2 survive longer (5400-5700 / 54-57%)
- Our agents: survive 2750-6239 steps (28-62%)
- Zero vibe transitions from ALL agents
- Cogs held 525K junction steps, 124 junctions gained

**Match 2: our best-scored match (score 46.6)**
- 6 evyIm-stuck15 + 2 evyIm-patience10
- Agent survival: 21-70% of 10K steps (high variance)
- Cogs held 466K junction steps, 107 gained
- Zero vibe transitions

**Match 3: weak partner match (score 21.4)**
- 2 ours + 6 ron.anticlips (weak partner)
- Ron's agents all die at 6-15% survival
- Cogs held only 214K junction steps, clips dominated (482K)
- Our 2 agents survived 23-63% but couldn't compensate

### Key online insights
1. Score = partner quality x junction holding time. Our variance (21.4 to 46.6) is dominated by partner quality.
2. Zero vibe transitions universally — top RL policies don't use role specialization. Pure movement wins.
3. Agent survival at 10K steps is the critical metric. Agents that survive longer hold more junctions.
4. Hearts are scarce: only 5 withdrawn in all matches. No crafting observed.
5. safaalver-softmax is automated: all model checkpoints from a single training run, incremental steps.

## Offline-to-online gap

1. **Offline best**: 8.63/episode (8-agent, 3K steps, v1EZZ neutral-only fix). Online best: #15, score 41.85.
2. **Gap WIDENED**: #5 to #15 due to new competitor. Gap to #1: 3.44pts to 7.55pts (18%).
3. **Submission lag is critical**: neutral-only fix (+129.5%) NOT uploaded. Auth blocked 6 sessions.
4. **Dual bottleneck**: (a) AUTH blocks scripted improvements, (b) RL too early to compete with safaalver.
5. **Scripted ceiling is ~42 online** even with improvements. RL is the only path to top-5.

## Current bottleneck

**AUTH (primary, blocking)**: 6th session. Every day without auth is a day the +129.5% fix sits un-submitted.

**RL maturity (secondary, strategic)**: safaalver proves well-trained RL dominates at 49.40. Our RL training at 793 held ticks vs their competition-ready models. RL needs #1 research priority once auth is fixed.

## Issues updated this session

- **#79**: CREATED. Submit neutral-only-align fix. Priority:1, blocked on #78.
- **#78**: Comment added — 6th session, new urgency from safaalver competition.
- **#75**: Note added — safaalver proves RL dominance online.
- **#41**: Note added — safaalver RL analysis.

## Code changes this session

- `aligner_agent.py:752`: Removed enemy junctions from align targets
- `machina_llm_roles_policy.py:146,546`: Same fix in LLM policy
- `README.md`: Updated leaderboard
- `docs/autoresearch_director/notes.md`: This file

## Open questions for next director

1. **Is auth fixed?** If yes: immediately submit as `lessandro-ohm-mani-padme-hum`.
2. **Should we merge lBgBD (HP retreat)?** +4.1% at 10K. May stack with neutral-only fix.
3. **RL training acceleration**: safaalver's `all_role_policy_v1shapeterr4` suggests shaped terrain reward. Can we replicate their approach?
4. **Branch cleanup**: 120+ remote branches. v1EZZ and lBgBD have useful work.
5. **New seasons?** beta-teams-tiny-fixed has only 10 entries — lower-competition.
