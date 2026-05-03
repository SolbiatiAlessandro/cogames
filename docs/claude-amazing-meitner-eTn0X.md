# Experiment Log: claude-amazing-meitner-eTn0X

## Issue: #61 — Agent longevity: survive 8000+ steps in 10k-step online matches

**2026-05-03T08:00: autoresearch starting, my plan is to...**

Work on issue #61 — agent longevity. Our agents die at 3000-5500 steps in 10k-step online matches, losing 45-65% of the game. The offline eval runs 3000 steps which hides this problem entirely.

### Key findings from code review:
1. **Aligner `_read_hp()` returns `None`** (aligner_agent.py:561) — HP retreat is completely disabled for aligners. The comment says "causes rapid oscillation near territory boundaries" but this means aligners have zero HP management.
2. **Miner HP retreat threshold is 25%** (llm_skills.py:846) — very aggressive, only retreats when nearly dead.
3. **Hub heart depletion**: SharedMap tracks `hub_hearts_withdrawn` but agents don't budget hearts for the full 10k game.

### Plan:
1. Run 3000-step baseline (standard)
2. Run 10000-step baseline to observe death patterns
3. Enable HP retreat for aligners with a better implementation that avoids oscillation
4. Tune miner HP retreat threshold higher
5. Add heart conservation logic

**2026-05-03T08:01: starting to run baseline**
