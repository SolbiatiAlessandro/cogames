# Experiment Log: claude-amazing-meitner-0j5Ye (Issue #41 — RL Policy Training)

## 2026-05-15T17:10: autoresearch starting, my plan is to...

Working on Issue #41: RL policy training. This is the highest priority issue — the scripted policy has hit a confirmed ceiling at ~42 online score, and all top policies are RL-trained.

Previous researchers incorrectly assumed this was blocked on GPU. The repo owner confirmed: "we don't need GPU, the model is small enough."

**Plan:**
1. Run the built-in LSTM training on CPU with small step counts to validate the pipeline works
2. Train for progressively larger step counts (10k, 100k, 1M)
3. Evaluate trained checkpoints offline against our scripted baseline
4. If results look promising, submit to the online tournament
5. Iterate on training hyperparameters and architecture

## 2026-05-15T17:10: starting to run baseline (scripted policy)

Running the current scripted policy to establish a baseline reward score.
