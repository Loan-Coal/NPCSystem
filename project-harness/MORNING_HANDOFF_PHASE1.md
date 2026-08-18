# Overnight Phase 1 â€” handoff

Run finished: 2026-08-18 03:09:28
Full log: `c:\Users\lohan\Documents\hackathons\NPCSystem\project-harness\overnight_logs\phase1_20260817_230022.log`

## What ran

1. **3-model judge panel** (EVAL-P21.1/P21.2 live wiring) against `k3_73e6c36`: **FAILED (exit 1) -- see c:\Users\lohan\Documents\hackathons\NPCSystem\project-harness\overnight_logs\panel_judge_20260817_230022.stderr.log**
   - Wrote `evals/generations/k3_73e6c36/judged.jsonl` (one row per judge per record).
   - Prior single-judge `judged.jsonl` backed up alongside it (`*.pre-panel-20260817_230022.bak`) and
     is also recoverable via `git checkout` since the file is tracked.
2. **check_label_survival.py snapshot** (self-check, not a post-regen check): exit 0,
   see `c:\Users\lohan\Documents\hackathons\NPCSystem\project-harness\overnight_logs\label_survival_snapshot_20260817_230022.log`.

## What did NOT run (by design)

- **EVAL-P20.4 (regen #1), EVAL-P22.1, EVAL-P22.2** â€” held for `Run-OvernightPhase2.ps1`,
  pending your read of
  `project-harness/SEED_REPRODUCTION_AND_ISSUE_165_BRIEF.md` and a decision on ISSUE-165 /
  the seed-reproduction gate. Short version: neither actually blocks regen #1 on the merits, but
  you asked to review before firing it â€” that brief is the review material.
- **EVAL-P21.3 (compute each judge's kappa vs. the 393 human labels)** â€” **there is no existing
  command for this.** `make eval-calibrate` computes per-*scorer* kappa from
  `labels_v1.jsonl` directly; it does not break results down by *judge model* within the
  panel's own verdicts. Getting the three numbers EVAL-P21.3 asks for (mixtral's kappa,
  qwen2.5:14b's kappa, llama3.1:8b's kappa, each vs. the 345 relevant human labels) needs a small
  new analysis step filtering the new `judged.jsonl` by `judge_model` and running it through
  the same confusion-matrix machinery `calibration.py` uses for scorers. That's real (if small)
  new code, not something to improvise inside an ops script â€” recommend a short, normal TDD task
  for it next session. The DECISIONS entry settling the judge is explicitly a human call either
  way (ROADMAP.md's own text), so this was never going to auto-write itself.

## Next step

Read the panel's actual verdicts/agreement numbers in `c:\Users\lohan\Documents\hackathons\NPCSystem\project-harness\overnight_logs\panel_judge_20260817_230022.stderr.log` and the report under
`evals/reports/` first. Then either:
- write the small per-judge-kappa analysis step and EVAL-P21.3's DECISIONS entry, or
- move on to `Run-OvernightPhase2.ps1` once you've decided on the seed-reproduction question
  (it doesn't depend on EVAL-P21.3 being finished first).
