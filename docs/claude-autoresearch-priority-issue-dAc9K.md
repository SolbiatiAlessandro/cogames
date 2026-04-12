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

