# Issue #73: A/B Test toEqP Improvements Online

## Baseline (navfix-cd3 / main)
- HUB_ALIGN_DISTANCE = 25
- HP_RETREAT_THRESHOLD = 0.70
- stuck_threshold = 20
- aligner_fraction = 0.5 (4A+4M)
- patience (no_progress_on_target_steps) < 3
- Junction scoring: travel + hub_dist * 0.2 (no spread/enemy bonus)

## 2026-05-14: autoresearch starting

Plan: Upload 6 isolated variants to beta-cvc tournament, each changing exactly one parameter from the navfix-cd3 baseline.

### Variants
| Variant | Change | Upload Name |
|---------|--------|-------------|
| A | stuck_threshold=15 | ax5wp-73a-stuck15 |
| B | 5A+3M (num_aligners=5) | ax5wp-73b-5a3m |
| C | HUB_ALIGN_DISTANCE=30 | ax5wp-73c-hub30 |
| D | enemy recapture priority (-8) | ax5wp-73d-enemy |
| E | HP retreat 0.65 | ax5wp-73e-hpret65 |
| F | spread bonus (-0.05) | ax5wp-73f-spread |
