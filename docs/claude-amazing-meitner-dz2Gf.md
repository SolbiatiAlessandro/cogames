# Experiment Log: claude/amazing-meitner-dz2Gf

Working on: Issue #77 — RAxer bug fix sweep + scripted policy optimization

## 2026-05-20 05:30: autoresearch starting

**Plan**: 
1. Port krCLo improvements (+4.4%) to this branch: 3A5M split, hearts5 accumulation, progress tracking fix, cooldown activation
2. Run baseline to confirm
3. Implement dynamic role switching — convert idle aligners to miners after junction saturation
4. This is the biggest untapped opportunity: junctions saturate at ~1200 steps, aligners idle for remaining 1800+ steps at 3K (8800+ at 10K online)

**Context from previous sessions**:
- Issue #76 (priority:1) is blocked on expired auth token (4th consecutive session)
- krCLo session found +4.4% with 3A5M + hearts5 + progress fix
- Junction saturation happens at ~1200 steps, all reward after that is pure hold time
- Offline eval has no active enemy clips — online competition is adversarial

## 2026-05-20 05:30: starting to port krCLo improvements and run baseline
