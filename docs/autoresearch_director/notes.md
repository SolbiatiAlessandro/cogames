# Director Notes
_Written: 2026-05-02 (Session 24)_

## What I observed

Could not run replay capture (mettagrid requires Bazel, unavailable in this environment). Used existing frames from April 28 (4 agents, 5.52 total reward at 1000 steps) plus TSV data and issue comments for analysis.

## Key findings this session

### 1. Server is FIXED
The `cogames.games` module error (#59) has been resolved. `ron.anticlips:v2` (uploaded May 2, 01:42 UTC) is completing matches on the beta-cvc season. Our old ohm v5-v10 submissions are permanently failed and won't be re-queued. We need new submissions.

No one on the leaderboard had uploaded after April 30, so the breakage was platform-wide, not just us.

### 2. Major 2-agent CvC breakthrough (aSOVe branch)
Branch `claude/amazing-meitner-aSOVe` achieved CvC 2-agent avg 49.69 (from baseline 9.50, +423%). Two researchers worked on #58 in parallel:
- `xfD6y`: SwitchableMiner + predicted station + fast get_heart → 43.65 avg, 8-agent confirmed safe
- `aSOVe`: predicted station + hub rotation + defend tuning → 49.69 avg, 8-agent NOT YET TESTED

The aSOVe approach is superior but needs 8-agent regression validation before merge. I created #60 with precise instructions.

### 3. v52 declining
v52 dropped from #29 (35.97) to #31 (35.62). Competition is getting stronger — new entries and existing policies getting more matches. We need to submit improvements.

### 4. New season: beta-teams-tiny-fixed
A new season appeared (created May 2) but status is `complete`. Has entries from slanky, slinky, Paz-Bot-9000. Worth monitoring but not actionable right now.

## Current bottleneck

**Merge + submit the aSOVe 2-agent fix.** This is the single highest-leverage action. The offline research is done (+423% CvC improvement). What remains is:
1. Validate 8-agent no-regression (one experiment)
2. Merge to main
3. Submit to tournament
4. Monitor online results

If the CvC improvement translates even partially to online scoring, we should see significant gains because the 2-agent catastrophe (9.16 avg) was the primary reason NiskB underperformed v52 online despite being better for 4+ agents.

## What I expected to happen vs. what I found

**Expected**: Server still broken, researchers stuck.
**Found**: Server is fixed AND two researchers produced excellent work on #58 without being blocked by the server (they worked on offline CvC experiments). Much better situation than expected.

**Expected**: No new experiment data since session 23.
**Found**: Two active branches (xfD6y and aSOVe) with 9+ experiments and dramatically improved 2-agent handling.

## Issues updated this session
- **#59**: Closed — server fixed, `ron.anticlips:v2` completing matches
- **#58**: Added director comment documenting aSOVe/xfD6y progress and merge plan
- **#55**: Closed as superseded by #60 — NiskB validation is now part of the combined submission
- **#56**: Added director update, kept at priority:2
- **#60**: CREATED (priority:1) — Validate aSOVe 8-agent + merge + submit as `lessandro-ohm-bekkenze-maha-bekkenze`

## Branches NOT merged (and why)
- **aSOVe**: Best 2-agent results (49.69 avg CvC). PENDING 8-agent validation. Merge via #60.
- **xfD6y**: Good 2-agent results (43.65 avg CvC), 8-agent confirmed safe. FALLBACK if aSOVe regresses.
- **7T3EK**: HP retreat experiments. ohm v4 at #45 — not competitive. Superseded by aSOVe/xfD6y.
- **NWni3**: Hub-distance weight (+2.62%), junction coordination. Untested online. Low priority after aSOVe.

## Priority stack
```
priority:1  #60  Validate aSOVe + merge + submit        <- NEXT RESEARCHER DOES THIS
priority:1  #58  2-agent match handling                  <- research done, merge via #60
priority:2  #56  Agent survival optimization             <- after #60 results come in
priority:2  #57  10k-step utilization                    <- after #60 results come in
priority:2  #41  RL policy training                      <- BLOCKED (needs GPU)
priority:3  #50, #53, #27-#31                            <- speculative
```

## Open questions for next director
1. **Did the aSOVe merge succeed?** Check if #60 was completed and what the online results look like.
2. **2-agent online translation**: The CvC experiment uses "2 ours + 6 starters" which simulates real online 2-agent matches. But online partner quality varies widely. How well does the 49.69 CvC avg translate?
3. **xfD6y vs aSOVe conflict**: Both branches modify the same files. If aSOVe merge fails, consider xfD6y as fallback (lower CvC score but 8-agent confirmed safe).
4. **beta-teams-tiny-fixed season**: Is this the next competition format? Should we target it?
5. **After 2-agent fix**: If online score reaches ~37-38, the next bottleneck becomes agent survival (#56) and 10k utilization (#57). These are harder problems that may require RL (#41).
