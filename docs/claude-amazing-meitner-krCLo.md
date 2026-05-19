# autoresearch: issue #77 — RAxer bug fix sweep evaluation

Branch: `claude/amazing-meitner-krCLo`
Target issue: [#77](https://github.com/SolbiatiAlessandro/cogames/issues/77) — priority:2

## Context

Issue #76 (priority:1, RL checkpoint submission) is blocked by expired Softmax auth token — confirmed 401 again this session. Falling back to highest-priority actionable issue.

Issue #77 asks us to evaluate 40+ bug fixes from the RAxer branch. The recommended approach is to cherry-pick the 4 critical bugs and evaluate offline.

## Plan

2026-05-19T17:15Z: autoresearch starting, my plan is to:
1. Run baseline on current main (8-agent, 3000 steps, 3-seed avg)
2. Cherry-pick the 4 critical bug fixes from RAxer branch
3. Evaluate with same seeds
4. If improved (>3.6 total = >10%), keep and consider full RAxer evaluation
5. If not improved, try individual bug fixes to isolate which help/hurt

## Log

2026-05-19T17:15Z: starting to run baseline
