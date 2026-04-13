# Autoresearch Issue 36: Agent Mortality Crisis

Branch: `claude/amazing-meitner-JWpsV`

**Issue direction:** ALL agents die before step 10,000 in every online match. Agents gain 0.75-18.6 hearts/agent vs dinky's 56.6. heart.withdrawn stuck at 5 (initial hub stock). The make_heart pipeline doesn't sustain agents through 10k steps.

**Success criteria (from issue):**
- Primary: ≥2 agents survive to step 10,000 in self-play
- Stretch: all 8 agents survive to step 10,000
- Online score increase of ≥50% after fix

**Root cause analysis:**
1. Hub starts with 5 hearts — depleted by step ~500
2. Cooldown-based retry exists (v13 from issue #16) but max 8 steps cooldown is too short at 10k scale
3. make_heart fires automatically when agents use hub AND hub has 7+ of each element
4. But: agents don't return to hub frequently enough after initial hearts depleted
5. Resource deposits may not be diverse enough (need 7 of EACH of 4 elements)
6. No feedback loop: agents don't know when make_heart created new hearts

**Suggested experiments from issue:**
- A: Force agents to return to hub every N steps to check for crafted hearts
- B: Reset hub_depleted flag after miners deposit enough for make_heart
- C: Add explicit make_heart skill call after sufficient deposits
- D: Track crafted-hearts-available counter and trigger get_heart when >0

---

## 2026-04-13T00:00:00Z: autoresearch starting, my plan is to...

**Plan:**
1. Run 10k-step baseline with current policy to measure agent mortality and heart throughput
2. Analyze why the make_heart pipeline stalls at 10k steps
3. Implement deposit-aware heart tracking: count total deposits per element, estimate hearts available
4. When estimated hearts > 0, reset get_heart cooldown for all aligners
5. Add periodic hub return: aligners return to hub every N steps regardless of cooldown
6. Test at 10k steps and measure survival + heart throughput

**Hypothesis:**
The current cooldown system (max 8 steps) is tuned for 1k-step episodes. At 10k steps, the problem isn't that agents retry too much — it's that they don't retry ENOUGH. After a few failures, the cooldown + explore loop means agents drift away from hub and never return. By tracking deposits and signaling when hearts should be available, we can close the feedback loop and keep the mining→make_heart→collect cycle going.

