# autoresearch: issue #77 — Dynamic Role Switching + Architectural Changes

Branch: `claude/amazing-meitner-v1EZZ`
Target issue: [#77](https://github.com/SolbiatiAlessandro/cogames/issues/77) — priority:2

## Context

Previous 7 sessions on #77 exhausted incremental parameter/mechanism tweaks, reaching a +3.9% ceiling after 55+ experiments. This session focuses on **architectural changes** that haven't been attempted:

1. **Dynamic role switching**: Convert aligners to miners after junction saturation
2. **Aligner idle detection**: Aligners that spend >N steps exploring without finding junctions switch to mining
3. **Multi-agent deposit coordination**: Stagger deposit trips to reduce hub congestion

Key finding from prior sessions: aligners spend 68% of time exploring, 84% of explore phases cap out without finding junctions. Junction alignment saturates by step ~1200. After that, aligners are pure dead weight.

## Plan

2026-05-21T08:00Z: autoresearch starting, my plan is to:
1. Run baseline with merged dz2Gf improvements (3-seed avg at 3000 steps)
2. Implement dynamic aligner→miner role switching after junction saturation
3. Test variations: switch threshold, partial vs full switching
4. If that works, try more architectural changes

## Log

2026-05-21T08:00Z: starting to run baseline
