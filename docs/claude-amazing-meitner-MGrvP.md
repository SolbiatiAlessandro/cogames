# Experiment Log: Issue #38 — 6+2 Startup Mortality Fix

Branch: `claude/amazing-meitner-MGrvP`
Issue: https://github.com/SolbiatiAlessandro/cogames/issues/38

## 2026-04-16 05:30: Autoresearch starting

**My plan:** Continue work on issue #38 (6+2 startup-mortality). The previous researcher (branch `claude/amazing-meitner-dtLLg`) identified the root causes and proposed v1-v8c fixes purely from code analysis with NO offline validation. My task is to:

1. Implement the highest-leverage fixes
2. Actually RUN offline experiments to validate them
3. Measure the impact on 8-agent scenarios

**Key findings from previous researcher:**
- Miner LLM call at `llm_miner_policy.py:313` is UNGUARDED — any OpenRouter error kills the agent
- Aligner LLM call already has try/except (line 209-214)
- Scout has no outer try/except wrapper
- In 6+2: agents 0-3 are aligners (safe), agent 4 is scout, agent 5+ are miners (crash-prone)
- `scripted_miners=False` default means miners make LLM calls that can crash them

**Planned fixes (prioritized by leverage):**
1. Wrap miner LLM call in try/except (same pattern as aligner)
2. Add defensive try/except to all step_with_state methods
3. `scripted_miners="auto"` — True when n_agents >= 6
4. `num_scouts="auto"` — 0 when n_agents >= 6 (scouts contribute less than another miner)

## 2026-04-16 05:30: Starting baseline run

Running 8-agent 200-step baseline on current code (main/V20) to reproduce mortality patterns...
