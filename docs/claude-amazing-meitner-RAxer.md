# Autoresearch: Issue #71 - Junction Control Efficiency (Session RAxer)

## Context
Working on issue #71: Junction control efficiency — 74% vs Softy's 84%.
Cannot run offline experiments (Python 3.11 vs 3.12 required).
Strategy: Integrate proven toEqP offline improvements into main code, upload variants to beta-cvc for online validation.

## 2026-05-18T10:00: autoresearch starting

My plan is to:
1. Integrate the best toEqP findings that were never merged to main (+76.6% offline)
2. Create multiple tournament variants for online A/B testing
3. Upload to beta-cvc and monitor results
4. Focus on: HUB_ALIGN_DISTANCE=30, aligner_fraction=0.6, enemy recapture, spread bonus

## 2026-05-18T10:00: starting to run baseline

Cannot run offline experiments (mettagrid requires Python 3.12, env has 3.11).
Will use online tournament as validation. Current online baseline: evyIm-73a-stuck15 at #5 (41.85).

## 2026-05-18T10:00: baseline result

Online baseline from previous sessions:
- evyIm-73a-stuck15: #5 at 41.85 (132 comp matches)
- navfix-cd3:v1: ~40.32 (23 matches)
- 2ag avg: 24.5, 4ag avg: 41.2, 6ag avg: 44.0
