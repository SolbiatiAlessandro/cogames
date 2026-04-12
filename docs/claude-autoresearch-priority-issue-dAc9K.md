# autoresearch: issue #25 — 8-Agent Scaling with Scripted Miners (4A4M)

Branch: `claude/autoresearch-priority-issue-dAc9K`
Target issue: [#25](https://github.com/SolbiatiAlessandro/cogames/issues/25) — priority:1, in-progress

## Plan

**2026-04-12 session start**: autoresearch starting, my plan is to pick up issue #25
(highest priority, in-progress, unblocked post PR #18). The issue success criteria
(overriding general mission reward):
- primary: `mission_reward_total > 4.0` at 1000 steps with 8 agents (0.50/agent avg)
- stretch: `> 6.0` total (0.75/agent)

History context (from issue comments & director notes):
- 8-agent pre-merge (session 4, main): 0.4195/agent = 3.356 total (4A4M scripted miners, machina_llm_roles)
- 8-agent post-merge (session 5, cross_role): 0.4043/agent = 3.234 total (4A4M LLM miners)
- Best hybrid never run: `cross_role` aligners + `scripted_miners=true`
- 3-agent best: 0.825/agent (6-seed avg, deterministic scripted with `llm_timeout_s=0.001`)
- Plateau at ~175 failed experiments on 3-agent — 8-agent unexplored
- Plot from comment #1: pre-merge 8A decelerated from 0.06/100→0.01/100 at step 700 due to hub depletion.

Key hypothesis chain to test:
1. **Hybrid config** (cross_role aligners + scripted miners) has never been run — it's the
   top-ranked "highest leverage" experiment in the director notes (Q1).
2. With hub depletion + make_heart cycle both present, the step-700 deceleration should
   vanish, and 0.06/100 could maintain through 1000 → 4.8 total (above the 4.0 target).
3. Next-level: try different aligner/miner splits (3A5M, 5A3M) on top of the hybrid.

## Environment setup notes

- Fresh container; mettagrid had to be built from scratch via bazel.
- Proxy required: bazel fetches `bcr.bazel.build` which is behind an auth+TLS-inspection egress.
  Workarounds applied:
  - Installed bazelisk to `$HOME/bin/bazel`.
  - Created `/root/.bazelrc` with `startup --host_jvm_args=...` entries for proxy host/port/user/pass
    plus `-Djdk.http.auth.tunneling.disabledSchemes=` so Java permits Basic auth on CONNECT.
  - Created `/root/custom_truststore.jks` containing the egress-gateway CA (imported from
    `/usr/local/share/ca-certificates/*.crt`) and pointed bazel there via
    `-Djavax.net.ssl.trustStore`. Without this, bcr.bazel.build TLS handshake fails (PKIX).
- Disabled optional Nim renderers (mettascope) by renaming their source dir — those are not
  needed for headless `-r log` runs.
- No `.env.openrouter.local` present. Running the "cross_role" policy therefore falls back
  to scripted behavior for all LLM calls. Session #24 comments on issue #25 showed that
  pure-scripted actually *outperforms* the LLM variant at 3-agent (0.816 vs 0.671), so this
  is fine for the 8-agent experiment.

## Log

- `2026-04-12T00:26Z`: autoresearch starting, plan logged above.
- `2026-04-12T00:40Z`: starting to run baseline.
- `2026-04-12T00:52Z`: **baseline result is 3.52 total (0.44/agent), 1000 steps, seed 42.**
  Config: `machina_llm_roles kw.num_aligners=4 kw.llm_timeout_s=30 kw.scripted_miners=true`
  (this is the literal config from the issue #25 body). 8 aligned junctions, 7 hearts
  withdrawn, 6 deaths total, 3400 cogs/aligned.junction.held.
  **Critical regression versus comment #21 finding reproduced:** `num_scouts` defaults to 1
  in `machina_llm_roles`, so we actually got 4A1S3M, not 4A4M. Agent 4 is the scout and was
  stuck for **661 of 1000 steps** (status.max_steps_without_motion=661, 804 action.failed).
  Comment #21 already recorded that setting `num_scouts=0` was worth ~+31% at 3-agent scale
  (seed 44 went 0.358 → 0.945). First experiment will fix this — cheapest free win.
- `2026-04-12T00:55Z`: starting new experiment loop — exp1 "num_scouts=0 + LLM on".
  Hypothesis: setting `kw.num_scouts=0` actually yields 4A4M (vs the buggy 4A1S3M) and
  unblocks agent 4 from stuck loops. Combined with the LLM now being reachable
  (OPENROUTER_API_KEY added), the aligner planner should make better choices when the
  hub depletes and miner balance goes lopsided. Note that session #24 suggested LLM was
  slightly worse than pure scripted at 3 agents, but that was at 3-agent where scripted
  is already tuned. At 8 agents with hub congestion, LLM planning *might* net-help.
  If LLM hurts, I'll disable via `kw.llm_timeout_s=0.001` in exp2.
- `2026-04-12T01:15Z`: **exp1 result: 5.55 total (0.69/agent), +58% vs baseline.**
  Primary target (>4.0) **EXCEEDED**. Stretch (>6.0) still 8% away.
  Notable: `cogs/aligned.junction.held=5936` (vs 3400), 9 junctions gained (vs 8), 8 hearts
  withdrawn, 4 miner deaths (down from 6). Agent 4 stuck count 11 vs 661 — bug confirmed
  fixed. LLM calls did succeed this time (nemotron-super). KEEP. Next: squeeze the last
  ~8% toward the stretch goal. Likely levers (priority order):
  1. Swap to `google/gemma-3-12b-it:free` — comment #23 showed +9.4% at 3-agent scale.
  2. Miner role split sweep: 3A5M (more mining → more hearts → more aligner throughput).
  3. Reduce `stuck_threshold` / speed up abandonment of stale get_heart — agent 0 hit 727
     action.failed at hub.
- `2026-04-12T01:22Z`: starting new experiment loop — exp2 "gemma-3-12b-it:free".
  Hypothesis: swapping aligner LLM model to `google/gemma-3-12b-it:free` gives the same
  +9.4% that comment #23 saw at 3-agent. With 4 aligners at 8-agent, faster responses
  mean more decisions per episode; even a fraction of that improvement lands us past the
  6.0 stretch. Config change only, no code diff.
- `2026-04-12T01:50Z`: **exp2 result: 4.72 total (0.59/agent) — WORSE than exp1 (5.55).**
  Hypothesis busted. Rereading comment #23 + #24 in context: the +9.4% was because gemma
  was rate-limited into silence, and *nemotron was also being rate-limited*, so both runs
  were effectively pure-scripted, and the small seed-level variance looked like a gemma
  win. In this session nemotron actually completes 1.5–4.5 s responses and the policy
  benefits from real decisions at hub-congestion points. **Discard c7f493a**, reset to
  ad049c2. Next: exp3 aligner/miner split sweep.
- `2026-04-12T01:55Z`: starting new experiment loop — exp3 "5A3M split".
  Hypothesis: exp1 had each of 4 aligners average only 2.25 alignments/1000 steps
  (9 junctions gained / 4). The map has plenty of neutral junctions (11 known early).
  With 3 scripted miners, heart production in exp1 was 8 hearts withdrawn — enough
  for 8 alignments. If the bottleneck is aligner throughput (hub trips, route
  contention) rather than heart supply, adding a 5th aligner and dropping a miner
  should yield more junctions, at modest heart cost. Target: >6.0 total (stretch).
  Config: `kw.num_aligners=5,kw.num_scouts=0,...`. Seed 42. 1000 steps.
- `2026-04-12T02:10Z`: **exp3 result: 3.44 total (0.43/agent) — WORSE than baseline even.**
  Gear contamination exploded: 3 aligner-lost events (vs 1 in exp1), 1 scout.gained, 2
  scrambler.gained (both picked up + lost). Agent 2 lost 1300 hp on the contamination
  journey. The extra 5th aligner has to route past additional stations and keeps bumping
  into scout/scrambler. `aligned.junction.held=3292` (vs exp1 5936). Clear DISCARD.
  Lesson: 4A4M seems locally optimal for this map layout; the bottleneck isn't aligner
  count. Next idea: try the **opposite** — 3A5M — which reduces station contention and
  leans on the extra miner for heart supply. If that also regresses, swing to exp4
  (stuck_threshold tune).
- `2026-04-12T02:13Z`: starting new experiment loop — exp4 "3A5M split".
  Hypothesis: with only 3 aligners competing for the aligner station, initial gear
  acquisition should be cleaner. 5 scripted miners will overproduce hearts (exp1 had
  7 deposit runs from 4 miners; 5 miners should comfortably match or exceed that).
  The question is whether 3 aligners can cover junction coverage as effectively as 4
  — if their throughput was 2.25 alignments each, 3 × 2.25 = 6.75 junctions, which
  would still be far above the 5-hearts-needed floor for 4.0 target. Seed 42 1000 steps.
- `2026-04-12T02:25Z`: **exp4 result: 5.84 total (0.73/agent) — NEW BEST (+5.2% over exp1).**
  9 junctions gained (same as exp1), but `aligned.junction.held=6299` (+6%). 7 heart
  withdrawals are still enough because 3 aligners make fewer hub trips. Critically:
  - no aligner gear losses (vs 1 in exp1, 3 in exp3)
  - only 3 deaths (vs 4 exp1, 6 baseline)
  - max stuck agent: 20 (vs 63 in exp1)
  This confirms 4A4M is not the local optimum for 8A; 3A5M is cleaner. KEEP. 97% of the
  way to stretch 6.0. Next: exp5 try pushing further with tuned `stuck_threshold` or
  retry with seed variety to check it's not a seed-42 fluke.
- `2026-04-12T02:30Z`: starting new experiment loop — exp5 "stuck_threshold=12 on 3A5M".
  Hypothesis: agent 0 in exp4 still had `action.failed=727` indicating it spammed the
  hub approach cell for ~70% of the episode. The `stuck_threshold` knob controls how
  many no-move steps before the skill exits stale. Lowering 20 → 12 should abandon
  stale get_heart faster and free the slot for unstuck/explore. Comment #22 in issue #25
  already found that `TEAM_SCARCE_MAX_EMPTY_STEPS=80` (similar idea on miner side) was
  worth +6.6% at 3-agent; this is the aligner analogue. Config adds
  `kw.stuck_threshold=12` to the exp4 best. Seed 42.
- `2026-04-12T02:43Z`: **exp5 result: 5.25 total (0.657/agent) — worse than exp4 (5.84).**
  Surprising failure mode: `aligned.junction.gained` went UP (9→10) but `held` went DOWN
  (6299→5566) and deaths DOUBLED (3→6, with 3 agents each dying twice). The too-early
  bailout kills mid-alignment attempts so junctions flip back to neutral/enemy, and
  aligners bouncing between targets expose themselves to clip damage for longer. The
  default 20 is the right floor for aligner persistence. Discard. Next: opposite
  direction — `stuck_threshold=28` (more patient).
- `2026-04-12T02:45Z`: starting new experiment loop — exp6 "stuck_threshold=28 on 3A5M".
  Exp5 proved less patience hurts because mid-alignment interruptions cost both the
  junction and HP. If the opposite is also true, more patience should stabilize the
  held junctions further and push past 6.0. Risk: a stuck aligner burns more cycles on
  a doomed target. Config: exp4 + `kw.stuck_threshold=28`. Seed 42 1000 steps.
- `2026-04-12T02:58Z`: **exp6 result: 6.71 total (0.839/agent) — STRETCH TARGET EXCEEDED.**
  +14.9% over exp4. Big numbers:
  - aligned.junction.gained: 13 (vs 9 exp4, vs 8 baseline) — +44%
  - aligned.junction.held: 7393 (vs 6299) — +17%
  - heart.withdrawn: 10 (vs 7) — matches the junctions gained
  - max action.failed: 343 (vs 727 exp1) — no more permanent hub-approach spam
  Deaths went up to 10 (vs 3 in exp4), mostly miners taking clip damage, but each
  additional junction is worth so much reward that the trade is very net-positive.
  KEEP. Now both the primary (>4.0) and stretch (>6.0) targets are hit on seed 42.
  Next: try `stuck_threshold=36` to see if there's more headroom, then multi-seed
  verification.
- `2026-04-12T03:02Z`: starting new experiment loop — exp7 "stuck_threshold=36 on 3A5M".
  The 20 → 28 step was a big win. Probing whether the trend keeps going. Hypothesis:
  36 is past the congestion-resolution horizon, so it should mostly match 28, but if
  it's meaningfully better that tells us the 28 bound isn't tight. Risk: doomed targets
  burn more of the 1000-step budget. Seed 42, single run.
- `2026-04-12T03:13Z`: **exp7 result: 6.29 total (0.786/agent).** Between exp4 (5.84) and
  exp6 (6.71), so 28 is the local maximum in this direction. 11 junctions gained (vs 13
  in exp6, -15%), `action.failed` peak climbed back to 476, confirming the "doomed target
  burns budget" risk. Discard; exp6 remains best. Next: multi-seed verification of exp6
  on seeds 43 and 44 to ensure the gain isn't seed-42 specific.
- `2026-04-12T03:15Z`: starting multi-seed verification loop for exp6 (3A5M + stuck=28).
  Running seeds 43 and 44 with the same config. If either drops below 6.0 total, the
  exp6 config overfits to seed 42 and I'll need to re-evaluate.
- `2026-04-12T03:30Z`: **exp8/exp9 multi-seed results:**
  - seed 42: 6.71 (exp6)
  - seed 43: 4.29 (+primary, -stretch)
  - seed 44: 3.76 (-primary)
  - **avg 4.92** (+40% over 3.356 pre-merge baseline, above primary but below stretch)

  The stretch-target result on seed 42 was significantly seed-specific. Both alternate
  seeds show more gear contamination (scout/scrambler picked up on the navigation path)
  and fewer junctions in the map, so fewer alignment opportunities. The `stuck=28` tune
  may or may not beat `stuck=20` on those seeds — need to isolate. Next: rerun exp4
  (stuck=20, 3A5M) on seed 43 and 44 as control, to see if the stuck=28 choice is
  actually helping or hurting on the harder seeds.
- `2026-04-12T03:33Z`: starting new experiment loop — exp10 "exp4 stuck=20 on seeds 43/44".
  Control experiment: did `stuck_threshold=28` actually help on seeds 43/44, or is it
  seed-42-specific? Running 3A5M stuck=20 on both seeds. If exp4 matches or beats exp6
  on those seeds, we should revert stuck_threshold back to 20 for the final config
  (trade a bit of seed-42 peak for better generalization).
- `2026-04-12T03:50Z`: **exp10 control results — stuck=28 confirmed net-better across 3 seeds.**
  | seed | stuck=20 | stuck=28 | Δ |
  | --- | --- | --- | --- |
  | 42 | 5.84 | **6.71** | +0.87 |
  | 43 | 4.02 | **4.29** | +0.27 |
  | 44 | 3.80 | 3.76 | -0.04 |
  | **avg** | **4.55** | **4.92** | **+0.37** |

  Stuck=28 is retained as the best config. The remaining headroom on seeds 43/44 is
  almost entirely in gear contamination: 1–2 scout/scrambler pickups each. That's
  a structural issue from issue #12 — routes to aligner/miner station cross other
  stations and a station step auto-equips the wrong gear. Attempting a targeted code
  fix next.
- `2026-04-12T04:00Z`: starting new experiment loop — exp11 "gear_up greedy fallback avoid hazards".
  Code change in `src/cogames/policy/aligner_agent.py`:
  - `_greedy_move_toward_abs` gains an `avoid_hazards` flag. When set, it refuses
    directions whose immediate step lands on a known hazard station, tries the
    orthogonal axis, and falls back to `_safe_wander` if both greedy options are
    contaminated.
  - The two `_gear_up` greedy fallbacks now pass `avoid_hazards=True`.
  Previously, if BFS-to-station failed (e.g. an adjacent cell is blocked by another
  agent), the fallback walked the aligner straight into the nearest scout/scrambler
  station and auto-equipped wrong gear. The multi-seed runs showed 1–2 such
  contamination events per episode on seeds 43 and 44. Expect: reduced
  `scout.gained`, `scrambler.gained`, and fewer `aligner.lost` events on seeds 43/44.
  Testing on all three seeds 42/43/44.
- `2026-04-12T04:20Z`: **exp11 results:**
  | seed | exp6 (stuck=28) | exp11 (+fix) | Δ |
  | --- | --- | --- | --- |
  | 42 | 6.71 | **7.38** | +0.67 |
  | 43 | 4.29 | 4.13 | -0.16 |
  | 44 | 3.76 | 3.60 | -0.16 |
  | **avg** | **4.92** | **5.04** | **+0.12** |

  Big win on seed 42 (new single-seed best 7.38, 0 contamination, 8228 held).
  On 43/44 contamination is unchanged (1 scout.gained, 1 scrambler.gained,
  1–2 aligner.lost each). The fix helps the BFS-fail path in `_gear_up` but
  43/44 contamination happens elsewhere — most likely in `_get_heart` which
  uses `avoid_hazards=False` intentionally. Net-avg positive so **keep**.
  Next: exp12 try `_get_heart` with `avoid_hazards=True` to see if it shuts
  the remaining contamination path without blocking hub access.
- `2026-04-12T04:30Z`: starting new experiment loop — exp12 "get_heart + align_neutral prefer hazard-free BFS".
  Code change in `aligner_agent.py`: both `_get_heart` and `_align_neutral` previously
  called BFS with `avoid_hazards=False` on the assumption that aligners already holding
  aligner gear couldn't be contaminated. The data refutes that: seeds 43/44 show 1–2
  mid-episode `aligner.lost` events per run with matching `scout.gained` /
  `scrambler.gained`, so walking through a wrong-role station does swap gear even for
  an already-equipped aligner. Fix: try `avoid_hazards=True` first and only fall back
  to `avoid_hazards=False` if the clean path is unreachable. Also apply the greedy
  fallback with `avoid_hazards=True`. This should zero out `scout.gained` /
  `scrambler.gained` on seeds 43/44. Multi-seed test.
- `2026-04-12T04:50Z`: **exp12 results:**
  | seed | exp11 | exp12 | Δ |
  | --- | --- | --- | --- |
  | 42 | 7.38 | 4.43 | **-2.95** |
  | 43 | 4.13 | 5.04 | +0.91 |
  | 44 | 3.60 | 5.43 | **+1.83** |
  | avg | 5.04 | 4.97 | -0.07 |
  | min | 3.60 | **4.43** | **+0.83** |

  Average dropped 0.07 but minimum jumped 0.83 and **all three seeds now clear the
  primary 4.0 target**, whereas exp11 failed on seed 44 (3.60 < 4.0). This is a
  much more robust config: the per-seed variance shrank dramatically and the
  worst seed is much closer to the best.
  Contamination zeroed out on seeds 42 and 44; seed 43 still has 1 scout + 1
  scrambler (likely a different path — possibly during `gear_up` with the greedy
  fallback + avoid_hazards, where both directions land on hazards and `safe_wander`
  then drifts into one anyway). Will investigate separately.
  The "average vs minimum" trade-off matters for issue target interpretation: the
  issue says "0.50/agent avg" meaning total 4.0. If that's per-run (min > 4.0 per
  seed), exp12 is the clear winner. If it's cross-seed avg, exp11 is 0.07 better.
  Keeping exp12 because robust minimum > fragile peak.
- `2026-04-12T05:00Z`: starting new experiment loop — exp13 "revert _align_neutral".
  Hypothesis: exp12 lost seed 42 (7.38 → 4.43, 13 → 7 junctions) mainly because
  `_align_neutral` now avoids hazards first. Neutral-junction targets are often on
  the far side of station clusters, so hazard-free BFS forces very long detours that
  eat the 1000-step budget. The data from exp12 shows contamination is mostly
  through `_get_heart` (fixed in exp12) and `_gear_up` (fixed in exp11), so aligning
  shouldn't need the hazard-free preference. Revert `_align_neutral` BFS to
  `avoid_hazards=False`, but keep the greedy fallback with `avoid_hazards=True` as a
  safety net. All three seeds.
- `2026-04-12T05:15Z`: **exp13 results: clear discard.**
  | seed | exp12 | exp13 | Δ |
  | --- | --- | --- | --- |
  | 42 | 4.43 | 4.94 | +0.51 |
  | 43 | 5.04 | **3.59** | **-1.45** |
  | 44 | 5.43 | **3.49** | **-1.94** |
  | avg | 4.97 | 4.01 | -0.96 |
  | min | 4.43 | 3.49 | -0.94 |

  Seed 42 recovered a little (junctions 7→13), but seeds 43/44 collapsed.
  Conclusion: the hazard-free preference in `_align_neutral` was actually doing
  real work on seeds 43/44 — aligners must pass near stations multiple times
  during alignment, and on those maps stations are placed badly enough that the
  default `avoid_hazards=False` path contaminates or damages aligners. The
  exp12 config is the right trade-off. Restore `aligner_agent.py` from 8e7792e
  and discard this branch tip.
  Next angles to try: (a) target `_get_heart` stuck-target detection — agent 0
  still spams the hub approach — and (b) seeds 45-47 to make sure exp12 isn't
  over-fit to seeds 42-44.

