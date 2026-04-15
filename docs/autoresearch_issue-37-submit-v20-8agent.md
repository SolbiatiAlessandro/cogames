# Autoresearch Issue #37 — Submit V20 Policy + Validate at 8 Agents / 10k Steps

Branch: `autoresearch/issue-37-submit-v20-8agent`
Started: 2026-04-15

## 2026-04-15 05:25 UTC: autoresearch starting

My plan is to:

1. **Setup**: Create branch (done), notebook, install cogames in `.venv_local` (done).
2. **Baseline at 8 agents / 1k steps** using the suggested config from the issue:
   `class=machina_llm_roles,kw.num_aligners=3,kw.num_scouts=0,kw.stuck_threshold=28,kw.llm_timeout_s=10`
   This is the untouched V20 stack (already merged on main). This tells us where we start at 8 agents.
3. **Baseline at 8 agents / 10k** to measure mortality + total reward at tournament-length.
4. **Iterate**: Sweep agent mixes (3A5M, 4A4M, 5A3M), tune skills/prompts based on replay analysis.
5. **Submit** a robustly-better-than-3.12 config via `cogames upload` to `beta-cvc` season.

## Context

- V20 stack is MERGED on main (commit 9b4c2d9). All V20 experiments were run on **3 agents** only.
- Issue-37 main ask: 8-agent validation is the gap. Prior best at 3A was ~1.90 reward.
- Current online rank: #291/363 score 3.12. Target: >= 5.0.
- The suggested baseline config is **3 aligners, 0 scouts, stuck=28, llm_timeout=10** → 5 miners (since 8-3=5).

## Sub-tasks discovered:
- Install cogames: `.venv_local/bin/cogames` (done).
- OpenRouter key at `/home/user/cogames/.env.openrouter.local` (exists).

## 2026-04-15 05:30 UTC: starting to run baseline

Command:
```
cogames run -m cogsguard_machina_1.basic -c 8 -p 'class=machina_llm_roles,kw.num_aligners=3,kw.num_scouts=0,kw.stuck_threshold=28,kw.llm_timeout_s=10' -e 1 -s 1000 --seed 42 --action-timeout-ms 10000
```

## 2026-04-15 05:40 UTC: baseline result = 0.767/agent = 6.14 total reward

**Baseline V20 merged at 8A 1k seed=42**
- per_episode_per_policy_avg_rewards = **0.767** (per-agent)
- Total reward = 8 * 0.767 ≈ **6.14**
- Episode stats: 7 aligned junctions, 8 aligned.junction.gained, 7 hearts withdrawn, 6 total deaths (0.75/agent).
- Deposits: carbon=72, oxygen=5, germanium=107, silicon=160. **Oxygen deposits are catastrophically low.**
- Move failure rate: 209/1000 = ~21% (matches online data). 788 moves succeed.
- max_steps_without_motion = 28.6 (matches stuck_threshold=28).
- action_timeouts = 14.

**Interpretation:**
- We're above the 0.5/agent target already (6.14 total > 4.0 target).
- Online (current): 3.12. Offline total: ~6.14 — but online score appears to be roughly 0.5x to 1x of total offline reward (Dinky online 27.21 is way above our offline).
- Session 7 best at 8A was reportedly 7.96 at 1k — we're at 6.14, so there IS regression from V20 team-scarce coordination or heart queue possibly.
- **Oxygen deposit is 5 vs carbon 72/germanium 107/silicon 160.** Oxygen extractors exist (objects.oxygen_extractor=40) but miners aren't reaching them. Element imbalance is the #1 leak.

**Next experiments:**
1. Try 4A4M (more aligners, fewer miners — maybe easier coordination).
2. Try 3A5M seed 43, 44 to check variance.
3. 10k validation at 3A5M seed 42 (mortality check).
4. Investigate oxygen imbalance in replay.
