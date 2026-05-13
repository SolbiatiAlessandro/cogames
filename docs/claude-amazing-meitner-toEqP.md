# Experiment Log: claude-amazing-meitner-toEqP

## Issue #71: Junction control efficiency — 74% vs Softy's 84%

### Goal
Improve junction control fraction from ~74% to 80%+ by optimizing aligner behavior, coordination, and junction acquisition efficiency.

---

## 2026-05-13 05:15: Autoresearch starting

My plan is to improve junction control efficiency by:
1. Investigating SharedMap coordination (currently NOT passed to aligners in MachinaRolesPolicy)
2. Optimizing heart pipeline (more hearts per trip = fewer hub returns)
3. Improving junction prioritization (cascade order, TSP-like routing)
4. Testing more aligners (3A+5M or 4A+4M vs current 2A+6M)

## 2026-05-13 05:17: Starting baseline run

Running 3-episode scrimmage with machina_roles, 8 agents, 3000 steps, seeds via episodes.

### Baseline Results (machina_roles, 2A+6M, 3000 steps)
- Episode rewards: 0.557, 0.611, 0.575
- Average: 0.581
- Junction held (cogs): 2809 avg
- Junction gained: 2.94 avg
- Hearts withdrawn: 5.0 avg
- Clips junction held: 183,120 avg (clips dominate)

Key observation: With only 2 aligners and no SharedMap coordination, junction control is extremely low. Aligners likely duplicate effort and waste time.

### Corrected Baseline (machina_llm_roles, 4A+4M scripted, 3000 steps)
- Episode rewards: 3.454, 1.234, 3.381
- Average: 2.690
- Junction held (cogs): 23,897 avg
- Junction gained: 53.7 avg
- Hearts withdrawn: 347 avg
- Clips junction held: 183,120 avg

---

## Experiment 1: Increase heart accumulation to 5

2026-05-13 05:28: Starting experiment. Hypothesis: Aligners make too many hub trips. Currently they collect 3 hearts, align 3 junctions, then return. With 5 hearts per trip, they make ~40% fewer hub trips and spend more time aligning junctions.
