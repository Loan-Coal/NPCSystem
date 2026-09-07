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

# 2. export labelling batches (25 items per batch), stratified so the
#    export refuses (no batch, exit 1) any judge whose best-case ceiling
#    cannot clear DEC-260's adequacy floor — the unguarded `label-export`
#    verb that skipped this check was retired.
make label-export-stratified TRANSCRIPT=$GEN/outputs.jsonl OUT_DIR=evals/calibration/batches

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
#    label-import REFUSES to overwrite a labels file holding human verdicts.
#    First import: no flag needed. Every later import: add --merge, which
#    refreshes scorer_verdict + the transcript passthrough fields and preserves
#    every human verdict. This is what makes fixing a judge's criteria and
#    re-judging cost zero relabelling.
make label-import RAW=evals/calibration/raw_labels.jsonl TRANSCRIPT=$GEN/outputs.jsonl \
                  JUDGED="$GEN/judged.jsonl $GEN/deterministic_judged.jsonl" MERGE=1

# 5. adjudicate (4-6 h, resumable) then report
make eval-adjudicate
make eval-calibrate
```

## Record identity

Transcript `record_id` (`<case>:<kind>:<index>`) omits `repetition`, so a k-repeat run emits k
records sharing one id with *different* response text. Everything downstream of `label-export-stratified`
therefore keys on the composite `<record_id>#r<n>` (see `evals/record_identity.py`). Joining on the
bare `record_id` silently keeps only the last repetition and attaches labels to the wrong output.
