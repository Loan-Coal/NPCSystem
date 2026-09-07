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

# 3. label (measurement-remediation Phase 5, DEC-272). Resumable: a batch whose rows are
#    already in OUT is skipped, so rerun the same command after any interruption.
#    Add DRY_RUN=1 first to see exactly which batches would be sent.
make prelabel BATCH_DIR=evals/calibration/batches OUT=evals/calibration/raw_labels.jsonl GEN_ID=<gen_id>

#    This replaced a hand-run PowerShell loop that passed prompt+batch on the command
#    line. Do not go back to that: the largest exported batch (37,420 chars) plus the
#    Opus prompt (15,565) is 52,985 chars, past Windows' 32,767-char command-line limit,
#    so the biggest batches could not be labelled that way at all. `make prelabel` sends
#    the prompt on the CLI's stdin, which has no such limit, drops non-JSON lines,
#    validates every row against the importer's own schema before writing, and appends a
#    provenance line (prompt sha256, model, gen_id) to <OUT>.log.

# 4. join into the real artifact (pass BOTH judged files)
#    label-import REFUSES to overwrite a labels file holding human verdicts.
#    First import: no flag needed. Every later import: add --merge, which
#    refreshes scorer_verdict + the transcript passthrough fields and preserves
#    every human verdict. This is what makes fixing a judge's criteria and
#    re-judging cost zero relabelling.
make label-import RAW=evals/calibration/raw_labels.jsonl TRANSCRIPT=$GEN/outputs.jsonl \
                  JUDGED="$GEN/judged.jsonl $GEN/deterministic_judged.jsonl" MERGE=1

# 5. BEFORE adjudicating, check the push is worth it (DEC-272). This reports, per scorer,
#    what adjudicating the pending pre-labels would yield against DEC-260's floor —
#    including which scorers a keep/flip pass cannot lift at all, because their pending
#    pre-labels are all on one side and the case set contains no failures to find.
make adjudication-yield

# 6. adjudicate (4-6 h, resumable) then report
make eval-adjudicate
make eval-calibrate
```

## Record identity

Transcript `record_id` (`<case>:<kind>:<index>`) omits `repetition`, so a k-repeat run emits k
records sharing one id with *different* response text. Everything downstream of `label-export-stratified`
therefore keys on the composite `<record_id>#r<n>` (see `evals/record_identity.py`). Joining on the
bare `record_id` silently keeps only the last repetition and attaches labels to the wrong output.
