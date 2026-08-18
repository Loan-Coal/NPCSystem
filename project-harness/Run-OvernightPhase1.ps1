# Phase 1 overnight run — 3-model judge panel over evals/generations/k3_73e6c36.
#
# Ops script, not repo tooling: deliberately outside the TDD/300-line/docstring
# discipline that applies to scripts/ and evals/. Lives in project-harness/ rather
# than a session scratchpad so the next run uses the same, reviewed copy.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File project-harness\Run-OvernightPhase1.ps1
#
# CHANGES vs the 2026-08-17 version (all four are fixes for what that run exposed):
#   1. Branches on evals/generations/<gen>/run_status.json, NOT the exit code. Exit 1
#      means "the pass completed and some cases missed expectations" — a real result,
#      not a crash. The old script read it as an infra failure and halted Phase 2 over
#      a 194/210 pass. Only status == "error" now stops the run. (DEC-189)
#   2. Backs up BOTH panel outputs and expects the two-file layout: judged.jsonl
#      (consensus, one row per record) + judged_panel_votes.jsonl (one row per seat).
#      (ISSUE-175, option (b))
#   3. Surfaces Fleiss kappa in the handoff, not just raw agreement — raw agreement is
#      inflated by the ~95% pass base rate. (DEC-188)
#   4. Records wall-clock duration; the 2026-08-17 pass took 4h09m against a ~2.5h
#      budget, so the H8 runbook estimate needs the real number.
#
# What this does NOT include, by design: EVAL-P20.4 (regen #1), EVAL-P22.1, EVAL-P22.2
# — those are Run-OvernightPhase2.ps1, held pending the seed-reproduction / ISSUE-165
# decision in project-harness/SEED_REPRODUCTION_AND_ISSUE_165_BRIEF.md.

# $ErrorActionPreference is deliberately "Continue", not "Stop": in PowerShell 5.1,
# redirecting a native command's stderr under "Stop" wraps EVERY stderr line (progress
# spinners, warnings) in a terminating NativeCommandError — ollama pull's progress bar
# killed an earlier version of this script on its first frame. Native-command failures
# are checked explicitly via $LASTEXITCODE / $proc.ExitCode instead.
$ErrorActionPreference = "Continue"
$RepoRoot = "c:\Users\lohan\Documents\hackathons\NPCSystem"
Set-Location $RepoRoot

$StampDir = Join-Path $RepoRoot "project-harness\overnight_logs"
New-Item -ItemType Directory -Force -Path $StampDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $StampDir "phase1_$Stamp.log"

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

Write-Log "=== Phase 1 overnight run starting ==="
Write-Log "Log file: $LogFile"

# --- Step 1: preflight ------------------------------------------------------
Write-Log "Preflight: checking Ollama is reachable ..."
$models = & ollama list 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    Write-Log "FATAL: 'ollama list' failed -- Ollama does not appear to be running. Start it and re-run."
    Write-Log $models
    exit 2
}
Write-Log "ollama list:`n$models"

if ($models -notmatch "llama3\.1:8b") {
    Write-Log "llama3.1:8b not found locally -- pulling now (~4.9GB; progress prints below, not captured to the log) ..."
    & ollama pull llama3.1:8b
    if ($LASTEXITCODE -ne 0) {
        Write-Log "FATAL: 'ollama pull llama3.1:8b' failed (exit $LASTEXITCODE)."
        exit 2
    }
    Write-Log "llama3.1:8b pulled successfully."
} else {
    Write-Log "llama3.1:8b already present."
}

foreach ($required in @("mixtral:8x7b", "qwen2.5:14b")) {
    if ($models -notmatch [regex]::Escape($required)) {
        Write-Log "FATAL: required panel model '$required' is not pulled locally. Pull it and re-run."
        exit 2
    }
}
Write-Log "All three panel models present: mixtral:8x7b, qwen2.5:14b, llama3.1:8b."

$env:JUDGE_TIMEOUT_SECONDS = "600"
Write-Log "JUDGE_TIMEOUT_SECONDS set to 600 (per-call timeout; matchers.py:_run_binary_judge applies this to every httpx.post to Ollama)."

# --- Step 2: back up the current panel artifacts ----------------------------
$GenDir = Join-Path $RepoRoot "evals\generations\k3_73e6c36"
$JudgedPath = Join-Path $GenDir "judged.jsonl"
$VotesPath = Join-Path $GenDir "judged_panel_votes.jsonl"
$StatusPath = Join-Path $GenDir "run_status.json"

foreach ($artifact in @($JudgedPath, $VotesPath, $StatusPath)) {
    if (Test-Path $artifact) {
        $Backup = "$artifact.pre-panel-$Stamp.bak"
        Copy-Item $artifact $Backup
        Write-Log "Backed up $(Split-Path $artifact -Leaf) to $(Split-Path $Backup -Leaf) (also recoverable via git)."
    }
}

# --- Step 3: the panel judge pass -------------------------------------------
# Start-Process with -RedirectStandardOutput/-RedirectStandardError writes directly to
# real files at the OS level -- no PowerShell pipe in the loop. `*>&1 | Tee-Object` on a
# long-running native process hung the 2026-08-17 first attempt for 3h+ with zero
# progress (child blocked on a full OS pipe PowerShell was not draining) and mangled the
# log to UTF-16. Do not reintroduce a pipe here.
#
# No overall wall-clock cap: the safety net is JUDGE_TIMEOUT_SECONDS=600 applied per
# Ollama call inside matchers.py:_run_binary_judge, so a stuck call surfaces as a logged
# infra failure (score=None -> inconclusive) and the pass moves on.
Write-Log "Starting 3-model judge panel against k3_73e6c36 (mixtral:8x7b -> qwen2.5:14b -> llama3.1:8b, sequential) ..."
Write-Log "EVAL-P21.1/P21.2 live wiring. Writes judged.jsonl (consensus, 1 row/record), judged_panel_votes.jsonl (1 row/seat/record) and run_status.json."
Write-Log "Expect ~4h based on the 2026-08-17 measured run (4h09m), not the original ~2.5h estimate."

$JudgeArgs = @(
    "-m", "evals", "judge",
    "--transcript", "evals\generations\k3_73e6c36\outputs.jsonl",
    "--reports", "evals\reports",
    "--json-out", "evals\generations\k3_73e6c36\judged.jsonl",
    "--panel"
)
$PanelStdout = Join-Path $StampDir "panel_judge_$Stamp.stdout.log"
$PanelStderr = Join-Path $StampDir "panel_judge_$Stamp.stderr.log"

$PanelStart = Get-Date
$proc = Start-Process -FilePath $Python -ArgumentList $JudgeArgs -WorkingDirectory $RepoRoot `
    -NoNewWindow -PassThru -Wait -RedirectStandardOutput $PanelStdout -RedirectStandardError $PanelStderr
$PanelExit = $proc.ExitCode
$PanelDuration = (New-TimeSpan -Start $PanelStart -End (Get-Date))
Write-Log ("Panel judge pass exited with code {0} after {1:hh\:mm\:ss}." -f $PanelExit, $PanelDuration)

# --- Step 3b: read run_status.json, NOT the exit code -----------------------
# This is the fix for the 2026-08-17 false alarm. status "gate_failed" means the
# measurement succeeded and some cases missed expectations -- Phase 2 may proceed.
# Only "error" (or a missing status file) means the harness did not complete.
$Status = $null
$StatusText = "MISSING"
if (Test-Path $StatusPath) {
    $Status = Get-Content $StatusPath -Raw | ConvertFrom-Json
    $StatusText = $Status.status
    Write-Log "run_status.json: status=$($Status.status) cases=$($Status.cases_passed)/$($Status.cases_total) kappa=$($Status.fleiss_kappa) raw_agreement=$($Status.raw_agreement)"
} else {
    Write-Log "WARNING: no run_status.json at $StatusPath -- treating as an error."
}

$MeasurementValid = ($StatusText -eq "ok") -or ($StatusText -eq "gate_failed")
if (-not $MeasurementValid) {
    Write-Log "HARNESS ERROR (status=$StatusText). Stopping Phase 1 -- do not proceed to Phase 2 until this is understood."
    Write-Log "stdout: $PanelStdout"
    Write-Log "stderr: $PanelStderr"
} elseif ($StatusText -eq "gate_failed") {
    Write-Log "Quality gate not met ($($Status.cases_passed)/$($Status.cases_total) cases passed) -- this is a RESULT, not a failure. Measurement is valid; Phase 2 may proceed."
} else {
    Write-Log "All cases passed the gate. Measurement is valid; Phase 2 may proceed."
}

# --- Step 4: label-survival snapshot (self-check only) ----------------------
Write-Log "Snapshotting check_label_survival.py (self-check against current transcript) ..."
$SurvivalLog = Join-Path $StampDir "label_survival_snapshot_$Stamp.log"
$SurvivalOutput = & $Python "scripts\check_label_survival.py" 2>&1 | Out-String
$SurvivalExit = $LASTEXITCODE
Set-Content -Path $SurvivalLog -Value $SurvivalOutput -Encoding utf8
Write-Log $SurvivalOutput
Write-Log "check_label_survival.py exited with code $SurvivalExit (output: $SurvivalLog)."

# --- Step 5: morning handoff -------------------------------------------------
$Handoff = Join-Path $RepoRoot "project-harness\MORNING_HANDOFF_PHASE1.md"
$PanelSummary = if (-not $MeasurementValid) {
    "**HARNESS ERROR (status=$StatusText)** -- measurement invalid, see $PanelStderr"
} elseif ($StatusText -eq "gate_failed") {
    "**COMPLETED, gate not met** -- $($Status.cases_passed)/$($Status.cases_total) cases passed. Measurement is valid."
} else {
    "**COMPLETED, gate met** -- $($Status.cases_passed)/$($Status.cases_total) cases passed."
}
$KappaLine = if ($Status -and $null -ne $Status.fleiss_kappa) {
    "Fleiss kappa **$([math]::Round($Status.fleiss_kappa, 3))** (chance-corrected; the headline), raw pairwise agreement $([math]::Round($Status.raw_agreement, 3))"
} else {
    "no agreement statistics recorded"
}

@"
# Overnight Phase 1 — handoff

Run finished: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Panel duration: $("{0:hh\:mm\:ss}" -f $PanelDuration)
Full log: ``$LogFile``

## What ran

1. **3-model judge panel** (EVAL-P21.1/P21.2 live wiring) against ``k3_73e6c36``: $PanelSummary
   - Agreement: $KappaLine
   - ``evals/generations/k3_73e6c36/judged.jsonl`` — consensus, one row per record.
   - ``evals/generations/k3_73e6c36/judged_panel_votes.jsonl`` — one row per seat per record.
   - ``evals/generations/k3_73e6c36/run_status.json`` — machine-readable outcome.
   - Previous artifacts backed up as ``*.pre-panel-$Stamp.bak`` (also in git).
2. **check_label_survival.py snapshot** (self-check, not a post-regen check): exit $SurvivalExit,
   see ``$SurvivalLog``.

## How to read the result

``run_status.json`` has three statuses. ``gate_failed`` means the pass **completed** and some
cases missed expectations — that is a measurement, not a malfunction, and Phase 2 may proceed.
Only ``error`` invalidates the numbers. Do not branch on the exit code (DEC-189).

## What did NOT run (by design)

- **EVAL-P20.4 (regen #1), EVAL-P22.1, EVAL-P22.2** — held for ``Run-OvernightPhase2.ps1``,
  pending the seed-reproduction / ISSUE-165 decision in
  ``project-harness/SEED_REPRODUCTION_AND_ISSUE_165_BRIEF.md``.
- **EVAL-P21.3 (per-judge kappa vs the human labels)** — still needs a small new analysis step
  joining ``judged_panel_votes.jsonl`` (now carrying ``judge_model``, ``repetition``, ``case_id``
  and ``judge_kind`` per row) against ``labels_v1.jsonl`` through ``calibration.py``'s
  confusion-matrix machinery. The votes file is now in the right shape for it; the analysis step
  and the DECISIONS entry settling the judge are a normal TDD task plus a human call.

## Next step

Compare this run's ``run_status.json`` against the re-derived baseline from the 2026-08-17 run
(``judged.jsonl.legacy-6field.bak`` migrated by ``scripts/migrate_panel_judged.py``):
kappa 0.526, raw agreement 0.956, 329/345 records passed. A clean match confirms the rewritten
persistence layer reproduces the original measurement.
"@ | Set-Content -Path $Handoff -Encoding utf8

Write-Log "Wrote handoff: $Handoff"
Write-Log "=== Phase 1 overnight run complete ==="
if (-not $MeasurementValid) { exit 2 }
exit 0
