# Director Notes
_Written: 2026-04-19 (Session 12 — offline-to-online)_

## Offline observations
- Offline best unchanged: 8.133 total at 500 steps (1.02/agent), 4A4M scripted auto
- No new offline experiments since session 11
- Mining stuck fix (#40) merged, +55% at 3000 steps
- Repo code fixed: `llm_miner_policy.py` httpx import now wrapped in try/except

## Online observations
### BREAKTHROUGH: We have matches!
- v22 through v33 uploaded Apr 18-19, all getting matches on beta-cvc
- **Best rank: #68/123** (lessandro-scripted-v32, score=12.66 ±9.11, 20 matches)
- 13 of our policy versions appear on the leaderboard (ranks #68-#112)
- v34 is BROKEN: WebSocket 1011 error in all 4 qualifying matches (#43 created)

### Leaderboard context
- beta-cvc now has 123 entries (up from ~51 at session 11)
- Top 5: Gryffindor (40.82), Slytherin (40.73), Hufflepuff (40.11), Softy (38.28), dinky_hank (38.18)
- All top policies are pure RL
- beta-teams-tiny-fixed: 10 entries, top score 36.00 (Hufflepuff:v16). We have NO entries there.

### Match analysis (v33, 22 completed matches)
| Partner type | Score range | What happens |
|---|---|---|
| Strong RL (dinky_abe, Softy, Ron, Slytherin) | 25-49 | Partner carries, we contribute little |
| Medium (shweta.v34, anoop.abaddon) | 6-18 | Mixed, both contribute |
| Weak (shweta.v18/v31, anoop.chen/spectre/treant) | 0.3-1.3 | Both fail — this is our TRUE level |
| Self-play | 17-22 | 8 of our agents cooperating |

### Replay analysis
Analyzed 3 replays in detail:

**v33 vs Softy:v88 (score=41.80)**:
- 2 ours + 6 Softy. Our agents survive 3043-3076/10000 (30%). Softy agents: 4118-5362/10000 (41-54%).
- Zero vibe transitions for ALL agents (ours and Softy) — this is normal behavior, not a bug
- cogs/aligned.junction.gained: 37, cogs/aligned.junction.held: 66,416
- Our agents: 2023-2785 moves, 218-410 failures

**v33 vs dinky_bob (score=6.64)**:
- 2 ours + 6 dinky_bob (but replay showed all 8 as ours — agent assignment parsing issue)
- Element deposits: carbon=580, germanium=593, oxygen=596, silicon=620 (total 2389)
- Element balance excellent (1.07:1 ratio) — balanced mining work paying off
- Hearts withdrawn: 5 (hub initial only, no make_heart)

**v33 vs shweta.v18 (score=0.47)**:
- Our agents survive only 1540-1649/10000 (15%)
- With weak partner, we die even earlier — partner junction control protects us

## Offline-to-Online gap

1. **Offline best**: 8.133 total at 500 steps (1.02/agent). Online best: #68/123, score 12.66 per match.
2. **Translation**: Online score of 12.66 is INFLATED by strong partner carry. Our true per-agent contribution when paired with weak partners is ~0.5-1.3 — matching the offline predictions.
3. **The gap to top**: 3.2x from #1 (40.82 vs 12.66). But the true policy quality gap is 30-40x (our agents contribute ~1/agent vs top RL's ~40/agent).
4. **Agent mortality explains most of the gap**: Our agents survive 15-31% of episode. Even doubling survival to 60% would roughly double our contribution.

## Current bottleneck

**Agent mortality is THE online bottleneck** (#36, now priority:1).

Evidence:
- Our agents survive 1500-3100 steps out of 10000 (15-31%)
- Hearts withdrawn: 5 (hub initial only), no make_heart working online
- With strong partners who control junctions, we survive longer (3000+ steps)
- With weak partners, we die by step 1600

Secondary: RL training (#41) is the fundamental ceiling. Scripted can't compete with RL (3.2x gap minimum).

## Issues updated this session
- **#43**: CREATED (priority:1) — v34 regression, WebSocket crash
- **#42**: Downgraded to priority:2, partially resolved (v22-v33 work, repo code fixed)
- **#36**: UPGRADED to priority:1 — agent mortality confirmed as #1 online bottleneck with replay evidence
- **#40**: Commented with online mining stats (2389 deposits, 6x gap, excellent element balance)
- **#38**: Downgraded to priority:3 — subsumed by #36

## Priority stack
```
priority:1  #43  Fix v34 regression       <- SPAWN NEXT (diagnose crash, revert to v33)
priority:1  #36  Agent mortality           <- HIGHEST LEVERAGE (15-31% survival → target 60%)
priority:1  #41  RL policy training        <- BLOCKED (needs GPU)
priority:2  #42  httpx import             <- partially resolved, repo code fixed
priority:2  #40  Mining throughput         <- improved to 2389, 6x gap remains
priority:2  #39  Submission process        <- v22-v33 submitted successfully
priority:2  #27  Andre Von Huck / A*       <- validated
priority:2  #24  Balanced Mining           <- element balance now excellent
priority:3  #38 6+2 mortality | #32 Partner | #31 change_vibe (NOT a bug)
priority:3  #30 Self-play | #26 shweta | #12 Gear | #10-#23 various
```

## Open questions for next director

1. **What broke v34?** Compare v33 and v34 uploaded bundles. The error is WebSocket 1011 (internal error) during qualifying — same pattern as the old httpx crash. Did v34 introduce a new dependency?

2. **Can we improve survival?** #36 is now priority:1. The key is getting make_heart to work online. Hub depletes at ~step 500, then agents slowly die from HP loss. Need: mine → deposit → craft hearts → collect hearts cycle to work at 10k steps.

3. **Submit to beta-teams-tiny-fixed?** 10 entries, top score 36.00. We'd place last but get on a second leaderboard. Could be useful for testing policies in a different format.

4. **v32 vs v33**: v32 scores 12.66 (#68), v33 scores 11.84 (#72). What changed? v32 might be the better policy to build on.

5. **Self-play scores**: v33 self-play scores 17-22. This is actually decent and suggests our policy works well when ALL agents are ours. The weakness is in cooperative matches where we get only 2 agents.

6. **RL training**: Still the fundamental ceiling. When will GPU compute be available? Even a basic LSTM policy trained for 1M steps would likely beat our scripted approach.
