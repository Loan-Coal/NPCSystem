# Calibration pass — how to run

Measures whether the automated scorers can be trusted, by comparing each scorer's own verdict
against a human verdict on the same output.

`LABEL_PROMPT.md` is **prompt-only** and is piped verbatim to the labeller. Never put run
instructions in it — anything in that file becomes something the model may answer instead of
labelling. That failure mode cost a full labelling run once already.

## Pipeline

```bash
GEN=evals/generations/<gen_id>

# 1. verdict sources — BOTH are required.
#    judge.jsonl covers only tone/affirms/refusal (~38% of records);
#    the deterministic matchers need their own replay pass or label-import
#    will fail with MissingVerdictError.
make eval-judge TRANSCRIPT=$GEN/outputs.jsonl GEN_ID=<gen_id>
make eval-deterministic-verdicts TRANSCRIPT=$GEN/outputs.jsonl GEN_ID=<gen_id>

# 2. export labelling batches (25 items per batch)
make label-export TRANSCRIPT=$GEN/outputs.jsonl OUT_DIR=evals/calibration/batches

# 3. label. Filter to '{'-leading lines: the model occasionally prepends prose or a
#    ```jsonl fence despite the prompt, and label-import rejects any non-JSON line.
#    -Encoding utf8 is required; PowerShell's default codepage corrupts the file.
foreach ($b in Get-ChildItem evals/calibration/batches/batch_*.json) {
  $prompt = (Get-Content evals/calibration/LABEL_PROMPT.md -Raw) + "`n`n<BATCH>`n" + (Get-Content $b.FullName -Raw) + "`n</BATCH>"
  claude -p $prompt --model opus |
    Where-Object { $_ -match '^\s*\{' } |
    Add-Content evals/calibration/raw_labels.jsonl -Encoding utf8
}

# 4. join into the real artifact (pass BOTH judged files)
make label-import RAW=evals/calibration/raw_labels.jsonl TRANSCRIPT=$GEN/outputs.jsonl \
                  JUDGED="$GEN/judged.jsonl $GEN/deterministic_judged.jsonl"

# 5. adjudicate (4-6 h, resumable) then report
make eval-adjudicate
make eval-calibrate
```

## Dry run first (no Claude credits)

Exercises every stage with random labels. Use it after any change to the pipeline — it is how the
Windows encoding crash in `calibrate` and the repetition-collapse join bug were both caught.

```bash
make mock-calibrate GEN_ID=<gen_id>
```

Mock artifacts are stamped `mock-random-v1` / `adjudicated_at="MOCK"` and written to
`mock_*.jsonl`, so they can never be confused with a real pass. **The kappa it prints is
meaningless** — it only proves the plumbing moves data of the right shape.

## Record identity

Transcript `record_id` (`<case>:<kind>:<index>`) omits `repetition`, so a k-repeat run emits k
records sharing one id with *different* response text. Everything downstream of `label-export`
therefore keys on the composite `<record_id>#r<n>` (see `evals/record_identity.py`). Joining on the
bare `record_id` silently keeps only the last repetition and attaches labels to the wrong output.
