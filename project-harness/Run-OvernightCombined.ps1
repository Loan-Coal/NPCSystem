# Combined overnight run: Phase 1 (judge panel over k3_73e6c36) + Phase 2 (regeneration #1
# and the EVAL-P22 chain), with the new arm ALSO panel-judged.
#
# Ops script, not repo tooling: deliberately outside the TDD/300-line/docstring discipline
# that applies to scripts/ and evals/. Lives in project-harness/ so it survives sessions.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File project-harness\Run-OvernightCombined.ps1 -IUnderstand
#
# -SkipPhase1 skips the k3_73e6c36 panel re-judge (step 2). Use it when that step has already
# succeeded and a later step failed -- step 2 writes only k3_73e6c36/ and evals/reports/, and
# nothing in steps 3-8 reads either, so repeating it buys nothing.
#
# STEPS 9-10 (added 2026-08-20) close out Phase EVAL-P22B, the engine-iteration A/B track:
#   9.  EVAL-P22B.1 -- record arm 1 as the trend baseline (seconds).
#   10. EVAL-P22B.2 -- the false-positive check: run scripts/Run-EvalHarness.ps1 end to end
#       against an UNCHANGED engine and require exit 0 (~5h). If the gate fires on a run whose
#       engine did not change, its threshold is wrong and every later verdict is noise.
# EVAL-P22B.3 is a documentation edit and is PRINTED at the end, never performed -- re-pointing
# EVAL-P23's dependency before step 10 has passed would assert a prerequisite that is not true.
#
# ~10 HOURS for steps 1-8 (~6h with -SkipPhase1); steps 9-10 add ~5h, so a full pass is 11-15h.
# Starting 22:00 finishes around 08:00 for steps 1-8 alone. There is no slack; if you need slack,
# drop Step 2 (the k3_73e6c36 panel re-run) — it is confirmation of the rewritten
# persistence layer, not a prerequisite for anything downstream.
#
# SPLITTING ACROSS TWO NIGHTS is the expected mode at that length, and this script's own history
# is of runs dying midway. Two switches make it resumable:
#   -Through 9              stop after the trend baseline, skipping the ~5h step 10.
#   -ResumeGenId <gen_id>   skip steps 1-8 entirely and run 9-10 against an arm already generated
#                           and judged. Deliberately does NOT re-check the clean tree: by then it
#                           is dirty by design (see B1 below), so re-asserting it would abort 100%
#                           of the time. The engine and panel roster ARE re-checked.
#
# Night 1:  ... -IUnderstand -SkipPhase1 -Through 9
# Night 2:  ... -IUnderstand -ResumeGenId k3_<sha>_regen1
#
# ENCODING: this file is UTF-8 WITH BOM and must stay that way. It contains non-ASCII (em dashes),
# and PowerShell 5.1 reads a BOM-less .ps1 as ANSI -- which turned an em dash inside a string
# literal into a stray quote and made the whole script a parse error on 2026-08-20.
#
# WHY EACH FIX IS HERE (all four blockers found 2026-08-18 while scoping the combination):
#   B1  The clean-tree gate is checked ONCE, up front, and the SHA captured there. Phase 2's
#       original preflight re-checked it after Phase 1 had already written the git-tracked
#       evals/generations/k3_73e6c36/judged.jsonl — so a naive Phase1-then-Phase2
#       concatenation aborted 100% of the time. The gate's purpose (attribute the regen to a
#       known commit) is satisfied by capturing the SHA before anything writes.
#   B2  build_label_order.py now lives in scripts/ as real, tested repo tooling. It was
#       stranded in a session scratchpad that would have vanished.
#   B3  The NEW arm gets a panel judge pass, so EVAL-P22.1's ordering covers the full corpus
#       and arm 1 is measured on the same instrument as k3_73e6c36. build_label_order is
#       invoked with --require-both so a missing verdict source fails loudly instead of
#       silently emitting a deterministic-only "full corpus" ordering.
#   B4  `make eval-world-reset` runs before the regen. DEC-186: "Reseeding is mandatory
#       before judging behaviour" — the three seed targets are MERGE-idempotent and may not
#       overwrite epoch-sized ticks already in a graph that predates the ISSUE-165 fix.
#       The checked-in baseline was verified clean (0 epoch-sized integers) on 2026-08-18.
#
# What this does NOT do: EVAL-P22.3 (the Opus pre-labelling pass). Per ROADMAP/DEC-185 that
# is a paid, human-run session and is deliberately outside any automated pipeline.

param(
    [switch]$IUnderstand,
    [switch]$SkipPhase1,
    # Skip steps 1-8 entirely and run only steps 9-10 against an arm that already
    # exists. Steps 1-8 are ~6h with -SkipPhase1 (~10h without) and steps 9-10 add
    # ~5h, so a single unattended pass is now 11-15h -- and this script's own history
    # is of runs dying midway (paused containers, the POSIX-only make target, the
    # restore/tick-scheduler race). Splitting across two nights is the expected mode,
    # not the exception.
    [string]$ResumeGenId = "",
    # Stop after this step. Default 10 (the whole run). -Through 9 records the trend
    # baseline without spending the ~5h false-positive check.
    [int]$Through = 10
)

if (-not $IUnderstand) {
    Write-Host "This fires EVAL-P20.4 (regeneration #1), a real, budgeted, hard-to-undo spend,"
    Write-Host "and runs for roughly 10 hours."
    Write-Host "Re-run with -IUnderstand once you have decided to proceed."
    exit 1
}

# $ErrorActionPreference is deliberately "Continue": under "Stop", PowerShell 5.1 wraps every
# stderr line from a native command in a terminating NativeCommandError, and ollama pull's
# progress bar alone killed an earlier version of this script. Failures are checked explicitly.
$ErrorActionPreference = "Continue"
$RepoRoot = "c:\Users\lohan\Documents\hackathons\NPCSystem"
Set-Location $RepoRoot

$StampDir = Join-Path $RepoRoot "project-harness\overnight_logs"
New-Item -ItemType Directory -Force -Path $StampDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $StampDir "combined_$Stamp.log"
$RunStart = Get-Date

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

function Read-RunStatus {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $null }
    try { return Get-Content $Path -Raw | ConvertFrom-Json } catch { return $null }
}

function Test-MeasurementValid {
    param($Status)
    if ($null -eq $Status) { return $false }
    return ($Status.status -eq "ok") -or ($Status.status -eq "gate_failed")
}

function Wait-ApiHealthy {
    param([int]$TimeoutSeconds = 120)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 5 -UseBasicParsing
            if ($r.StatusCode -eq 200) { return $true }
        } catch { }
        Start-Sleep -Seconds 3
    }
    return $false
}

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

# ---------------------------------------------------------------------------
# Steps 9 and 10 (EVAL-P22B) -- defined as functions because -ResumeGenId runs
# them without steps 1-8.
# ---------------------------------------------------------------------------

function Invoke-TrendBaseline {
    <#  STEP 9 -- EVAL-P22B.1: record this arm as the trend baseline (seconds).

        Must run through the REPAIRED pipeline so row one carries fleiss_kappa,
        kappa_by_criterion and repeat_flips from the very first measurement --
        retrofitting a baseline row later loses kappa continuity from the start.
        --allow-no-baseline is correct here and only here: this IS the first row,
        so there is nothing comparable to gate against yet.
    #>
    param([string]$GenId, [string]$GenDir, [string]$StampDir)

    Write-Log "STEP 9/10: EVAL-P22B.1 -- recording $GenId as the trend baseline ..."
    $TrendLog = Join-Path $StampDir "trend_baseline_$GenId.log"
    & $Python (Join-Path $RepoRoot "scripts\record_trend_and_gate.py") `
        --gen-id $GenId --gen-dir $GenDir --allow-no-baseline *>&1 |
        Tee-Object -FilePath $TrendLog
    $exit = $LASTEXITCODE
    Write-Log "record_trend_and_gate.py exit $exit (output: $TrendLog)."

    # EVAL-P22B.1's stated validation, asserted here rather than left to the morning.
    $TrendFile = Join-Path $RepoRoot "evals\trend\trend_v1.jsonl"
    if (-not (Test-Path $TrendFile)) {
        Write-Log "STEP 9 FAILED: $TrendFile was not written."
        return @{ Exit = 9; Rows = 0; Kappa = $null }
    }
    $rows = @(Get-Content $TrendFile | Where-Object { $_.Trim() })
    $last = $null
    if ($rows.Count -gt 0) { try { $last = $rows[-1] | ConvertFrom-Json } catch { $last = $null } }
    if ($null -ne $last) {
        Write-Log "  rows=$($rows.Count) gen_id=$($last.gen_id) harness_version=$($last.harness_version) fleiss_kappa=$($last.fleiss_kappa)"
        if ($last.harness_version -eq "legacy_pre_p18_1") {
            Write-Log "  WARNING: harness_version is the legacy sentinel -- this row can never compare (ISSUE-186)."
        }
        if ($null -eq $last.fleiss_kappa) {
            Write-Log "  WARNING: fleiss_kappa is null -- the judge pass did not record panel metrics."
        }
    }
    return @{ Exit = $exit; Rows = $rows.Count; Kappa = $(if ($last) { $last.fleiss_kappa } else { $null }) }
}

function Invoke-FalsePositiveCheck {
    <#  STEP 10 -- EVAL-P22B.2: the false-positive check (~85 min gen + ~4h judge).

        Runs the harness end to end against an UNCHANGED engine. Exit 0 is the pass
        condition: if the gate fires on a run whose engine did not change, its
        threshold is wrong and every later verdict is noise. Exit 3 (instrument
        degraded) is a distinct and genuinely expected outcome with refusal_judge at
        kappa 0.225 (ISSUE-184) -- it is NOT an engine finding and must not send
        anyone debugging the engine.

        This depends on Run-EvalHarness.ps1's clean-tree precondition excluding the
        artifact directories: by now step 7 has written the tracked judged.jsonl, and
        this script's own step 1 documents the tree as dirty-by-design from there on.
    #>
    param([string]$StampDir)

    Write-Log "STEP 10/10: EVAL-P22B.2 -- false-positive check against an unchanged engine (~5h) ..."
    $HarnessLog = Join-Path $StampDir "false_positive_check_$Stamp.log"
    & powershell -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $RepoRoot "scripts\Run-EvalHarness.ps1") -K 3 *>&1 |
        Tee-Object -FilePath $HarnessLog
    $exit = $LASTEXITCODE

    switch ($exit) {
        0 { Write-Log "STEP 10 PASS: unchanged engine read as no-regression. The gate does not fire on noise." }
        1 { Write-Log "STEP 10 FAIL: the gate fired on an UNCHANGED engine. Its threshold is wrong -- every later verdict is noise until this is fixed. Do NOT treat this as an engine regression." }
        2 { Write-Log "STEP 10 SETUP ERROR: a precondition failed or there was no comparable baseline. Nothing was measured." }
        3 { Write-Log "STEP 10 INSTRUMENT DEGRADED: inter-judge agreement fell. Expected with refusal_judge at kappa 0.225 (ISSUE-184). Investigate the judge panel, not the engine." }
        default { Write-Log "STEP 10 UNKNOWN exit $exit." }
    }
    Write-Log "Run-EvalHarness.ps1 exit $exit (output: $HarnessLog)."
    return @{ Exit = $exit; Log = $HarnessLog }
}

function Write-CloseoutChecklist {
    <#  Phase EVAL-P22B.3 is a documentation edit, so it is PRINTED, never performed:
        re-pointing a dependency before the run it depends on has actually passed would
        assert a prerequisite that is not yet true. #>
    param([string]$GenId, [int]$HarnessExit)

    Write-Log ""
    Write-Log "=== EVAL-P22B.3 -- do these by hand, after reading the results above ==="
    Write-Log "  1. Tick EVAL-P20.4 / EVAL-P22.1 / EVAL-P22.2 / EVAL-P22B.1 in ROADMAP.md, naming gen_id $GenId."
    if ($HarnessExit -eq 0) {
        Write-Log "  2. Tick EVAL-P22B.2 (step 10 exited 0 -- the no-op check genuinely passed)."
        Write-Log "  3. EVAL-P23's 'Depends on:' line: replace EVAL-P22.4 with EVAL-P22B.2."
        Write-Log "     Note in EVAL-P23's Notes that the trend baseline is regeneration #1, not #2."
        Write-Log "     Drop EVAL-P23.1/.2/.3 from HUMAN GATE H10's 'Blocks:' list."
        Write-Log "     Effect: EVAL-P23 no longer transitively depends on an Opus spend."
    } else {
        Write-Log "  2. Do NOT tick EVAL-P22B.2 and do NOT re-point EVAL-P23 -- step 10 exited $HarnessExit."
        Write-Log "     Re-pointing the dependency now would assert a prerequisite that is not true."
    }
    Write-Log "  4. Update tests/unit/harness/test_roadmap_cursor.py's EXPECTED_FLAGS if any tick changes a flag."
}


Write-Log "=== Combined overnight run starting ==="
Write-Log "Log file: $LogFile"

# --- Resume path: steps 9-10 only, against an arm that already exists ---------
# Deliberately does NOT re-check the clean tree. By the time steps 1-8 have run,
# the tree is dirty by design (step 1 says so), so re-asserting it here would
# abort 100% of the time -- the same B1 defect a naive Phase1-then-Phase2
# concatenation had. The engine and the panel roster ARE re-checked: those are
# preconditions of the work about to happen, not of the work already done.
if ($ResumeGenId) {
    Write-Log "RESUME MODE: skipping steps 1-8, running steps 9-10 against $ResumeGenId."
    $GenId = $ResumeGenId
    $GenDir = Join-Path $RepoRoot "evals\generations\$GenId"
    if (-not (Test-Path $GenDir)) {
        Write-Log "FATAL: $GenDir does not exist. -ResumeGenId must name an arm that has already been generated and judged."
        exit 2
    }
    if (-not (Test-Path (Join-Path $GenDir "judged.jsonl"))) {
        Write-Log "FATAL: $GenDir holds no judged.jsonl -- the arm was generated but never judged, so it has no metrics to record."
        exit 2
    }
    if (-not (Wait-ApiHealthy -TimeoutSeconds 120)) {
        Write-Log "FATAL: engine is not answering /health. Step 10 regenerates against it."
        exit 2
    }
    $env:JUDGE_TIMEOUT_SECONDS = "600"

    $trend = Invoke-TrendBaseline -GenId $GenId -GenDir $GenDir -StampDir $StampDir
    $harnessExit = -1
    if ($Through -ge 10) {
        $fp = Invoke-FalsePositiveCheck -StampDir $StampDir
        $harnessExit = $fp.Exit
    } else {
        Write-Log "STEP 10/10: SKIPPED (-Through $Through)."
    }
    Write-CloseoutChecklist -GenId $GenId -HarnessExit $harnessExit
    Write-Log ("=== Resume run complete in {0:hh\:mm\:ss} ===" -f (New-TimeSpan -Start $RunStart -End (Get-Date)))
    exit $(if ($trend.Exit -ne 0) { $trend.Exit } elseif ($harnessExit -gt 0) { $harnessExit } else { 0 })
}

# --- Step 1: preflight, ONCE (B1) --------------------------------------------
Write-Log "Preflight: git tree must be clean and committed (checked once, here, not again later) ..."
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Log "FATAL: working tree is not clean:`n$gitStatus"
    Write-Log "H7's precondition requires a committed tree before spending a regeneration. Commit or stash first."
    exit 2
}
$Sha = (git rev-parse --short HEAD).Trim()
Write-Log "Tree clean at $Sha. This SHA is what the regeneration will be attributed to."
Write-Log "NOTE: later steps write tracked files (judged.jsonl). The tree will be dirty from here on, by design."

Write-Log "Checking Ollama and the panel roster ..."
$models = & ollama list 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    Write-Log "FATAL: 'ollama list' failed -- Ollama does not appear to be running."
    Write-Log $models
    exit 2
}
foreach ($required in @("mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b")) {
    if ($models -notmatch [regex]::Escape($required)) {
        Write-Log "FATAL: required panel model '$required' is not pulled locally. Pull it and re-run."
        exit 2
    }
}
Write-Log "All three panel models present."

$env:JUDGE_TIMEOUT_SECONDS = "600"
Write-Log "JUDGE_TIMEOUT_SECONDS=600 (per Ollama call, matchers.py:_run_binary_judge)."

$OldGenDir = Join-Path $RepoRoot "evals\generations\k3_73e6c36"

# --- Step 2: Phase 1 -- panel over k3_73e6c36 (~4h) --------------------------
# Confirmation that the rewritten persistence layer reproduces the re-derived baseline
# (kappa 0.526, raw agreement 0.956, 329/345). Not a prerequisite for Step 4 onward.
if ($SkipPhase1) {
    # Step 2 is an isolated island: it writes only k3_73e6c36/ and evals/reports/, and nothing
    # in steps 3-8 reads either. Skipping it after a successful run costs nothing downstream.
    Write-Log "STEP 2/10: SKIPPED (-SkipPhase1). Reading the existing k3_73e6c36 run_status.json instead."
    $P1Status = Read-RunStatus (Join-Path $OldGenDir "run_status.json")
    $P1Duration = New-TimeSpan -Seconds 0
    $P1Out = "(skipped)"; $P1Err = "(skipped)"
    if (Test-MeasurementValid $P1Status) {
        Write-Log "Existing Phase 1 measurement: kappa=$($P1Status.fleiss_kappa) agreement=$($P1Status.raw_agreement) cases=$($P1Status.cases_passed)/$($P1Status.cases_total)"
    } else {
        Write-Log "No valid existing Phase 1 measurement found -- continuing; nothing downstream depends on it."
    }
} else {
Write-Log "STEP 2/10: panel judge over k3_73e6c36 (~4h) ..."
foreach ($artifact in @("judged.jsonl", "judged_panel_votes.jsonl", "run_status.json")) {
    $p = Join-Path $OldGenDir $artifact
    if (Test-Path $p) { Copy-Item $p "$p.pre-combined-$Stamp.bak" }
}
$P1Out = Join-Path $StampDir "p1_panel_$Stamp.stdout.log"
$P1Err = Join-Path $StampDir "p1_panel_$Stamp.stderr.log"
$p1Start = Get-Date
$proc = Start-Process -FilePath $Python -ArgumentList @(
    "-m", "evals", "judge",
    "--transcript", "evals\generations\k3_73e6c36\outputs.jsonl",
    "--reports", "evals\reports",
    "--json-out", "evals\generations\k3_73e6c36\judged.jsonl",
    "--panel"
) -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -Wait `
  -RedirectStandardOutput $P1Out -RedirectStandardError $P1Err
$P1Duration = New-TimeSpan -Start $p1Start -End (Get-Date)
$P1Status = Read-RunStatus (Join-Path $OldGenDir "run_status.json")
Write-Log ("Phase 1 panel finished in {0:hh\:mm\:ss}, exit {1}." -f $P1Duration, $proc.ExitCode)
if (Test-MeasurementValid $P1Status) {
    Write-Log "Phase 1 measurement VALID (status=$($P1Status.status)) kappa=$($P1Status.fleiss_kappa) agreement=$($P1Status.raw_agreement) cases=$($P1Status.cases_passed)/$($P1Status.cases_total)"
    Write-Log "Baseline to compare against: kappa 0.526, agreement 0.956, 329/345."
} else {
    Write-Log "Phase 1 measurement INVALID -- continuing anyway: nothing downstream depends on it (see $P1Err)."
}
}

# --- Step 3: world reset + seeds (B4) ----------------------------------------
Write-Log "STEP 3/10: docker up, eval-world-reset, seed all three worlds ..."

# Docker Desktop's Resource Saver -- and host sleep -- PAUSE idle containers during a long
# GPU-bound step. `docker-compose up -d` cannot start a paused container: it fails with
# "Error response from daemon: cannot start a paused container, try unpause instead".
# That is exactly what killed the 2026-08-18 run at this line, AFTER step 2 had already
# spent 4h09m. Unpause first, then give the healthcheck time to clear the failures it
# accumulated while paused (the container reports `unhealthy` from stale probes for a
# while after resuming, which `up -d` also treats as a dependency failure).
$paused = @(docker ps -a --filter "status=paused" --format "{{.Names}}" 2>$null | Where-Object { $_.Trim() })
if ($paused.Count -gt 0) {
    Write-Log "Paused container(s) detected: $($paused -join ', ') -- unpausing ..."
    foreach ($c in $paused) {
        & docker unpause $c.Trim() 2>&1 | Out-String | ForEach-Object { Write-Log $_.Trim() }
    }
    Write-Log "Waiting 45s for healthchecks to clear stale failures from the paused period ..."
    Start-Sleep -Seconds 45
}

$dc = docker-compose up -d 2>&1 | Out-String
Write-Log $dc
if ($LASTEXITCODE -ne 0) { Write-Log "FATAL: docker-compose up -d failed."; exit 3 }

# DEC-186: stored epoch-sized ticks read as unreachably far in the future, which silently
# disables routine overrides. The MERGE-idempotent seed targets do not clear them; this does.
# `make eval-world-reset` is NOT usable from PowerShell/cmd. Its recipe is
#     MSYS_NO_PATHCONV=1 docker compose run --rm -v "$$PWD:/work" ...
# a POSIX inline env-var prefix. The Makefile sets no `SHELL :=`, so make uses cmd.exe here,
# which cannot parse it: "'MSYS_NO_PATHCONV' is not recognized as an internal or external
# command". This killed the 2026-08-19 01:57 relaunch at exactly this line. MSYS_NO_PATHCONV
# exists only to stop Git Bash mangling the /work path, so it is unnecessary under PowerShell
# -- invoke docker directly. The Makefile target is deliberately left alone: it works from Git
# Bash, which is its documented path (ISSUE-187). The other four make targets this script uses
# (demo-seed, seed-village-world, seed-tavern-world, mock-calibrate-oracle) are $(PYTHON)-based
# and were verified working from PowerShell on 2026-08-19.
# The app's tick scheduler PERSISTS the game tick to :WorldState (DEC-186), so the running app
# writes to Neo4j continuously. do_restore wipes the graph then CREATEs each snapshot node; if
# the scheduler recreates :WorldState inside that window the CREATE collides:
#   ConstraintValidationFailed: Node already exists with label `WorldState` and property id='world'
# That killed the 2026-08-19 22:19 run and left the graph PARTIALLY restored (139 of 248 nodes) --
# worse than not running at all. Stop the app for the duration. `docker compose run app` starts its
# own one-off container, so the restore still works while the service is stopped. Verified
# 2026-08-19: with the app stopped the restore completes cleanly (248 nodes, 233 relationships).
# Since 2026-08-20 (ISSUE-188 / DEC-192) do_restore is also ONE transaction and probes for a live
# writer for 12s before touching anything, so if this stop is ever removed the restore refuses
# cleanly (exit 2) instead of half-wiping the graph. The stop stays: it is what makes it pass.
Write-Log "Stopping the app service for the restore (its tick scheduler writes :WorldState -- DEC-186) ..."
& docker compose stop app 2>&1 | Out-String | ForEach-Object { Write-Log $_.Trim() }

Write-Log "Restoring the checked-in eval-world baseline (direct docker; bypasses the POSIX-only make target) ..."
$reset = & docker compose run --rm -v "${RepoRoot}:/work" -w /work app `
    python -m demo_game.snapshot --mode restore `
    --path /work/evals/fixtures/eval_world_baseline.json 2>&1 | Out-String
Write-Log $reset
if ($LASTEXITCODE -ne 0) { Write-Log "FATAL: eval-world-reset failed -- refusing to regenerate against a possibly stale-tick graph."; exit 3 }

# The seeds below hit the engine over HTTP, so the app must be back up AND answering before they
# run -- and the regen in step 4 needs it too. Wait on /health rather than assuming.
Write-Log "Restarting the app service ..."
$dcUp = docker-compose up -d 2>&1 | Out-String
Write-Log $dcUp
if (-not (Wait-ApiHealthy -TimeoutSeconds 180)) {
    Write-Log "FATAL: engine did not answer /health within 180s after the restore -- refusing to seed or regenerate."
    exit 3
}
Write-Log "Engine healthy again after the restore."

foreach ($seedTarget in @("demo-seed", "seed-village-world", "seed-tavern-world")) {
    $seedOutput = & make $seedTarget 2>&1 | Out-String
    Write-Log $seedOutput
    if ($LASTEXITCODE -ne 0) { Write-Log "FATAL: 'make $seedTarget' failed."; exit 3 }
}

$ApiKey = "eval-key-change-me"
$EnvFile = Join-Path $RepoRoot ".env"
if (Test-Path $EnvFile) {
    $match = Select-String -Path $EnvFile -Pattern '^API_KEY_SECRET=(.+)$' | Select-Object -First 1
    if ($match) { $ApiKey = $match.Matches[0].Groups[1].Value.Trim() }
}

$GenId = "k3_${Sha}_regen1"
$GenDir = Join-Path $RepoRoot "evals\generations\$GenId"
Write-Log "New gen_id: $GenId  (this is A/B ARM 1 -- the first run with a real harness_version and seed)"
if (Test-Path $GenDir) {
    Write-Log "FATAL: $GenDir already exists -- refusing to overwrite a prior run."
    exit 3
}

# --- Step 4: EVAL-P20.4 regeneration #1 (~85 min) ----------------------------
Write-Log "STEP 4/10: EVAL-P20.4 regeneration #1 (95 cases x k=3, ~85 min) ..."
$GenLog = Join-Path $StampDir "regen1_generate_$Stamp.log"
& $Python -m evals generate `
    --base-url "http://localhost:8000" --api-key $ApiKey `
    --cases "evals\cases" --fixture "evals\cases\anti_hallucination_demo.json" `
    --out "evals\generations" --run-id "latest" --gen-id $GenId --k 3 *>&1 | Tee-Object -FilePath $GenLog
if ($LASTEXITCODE -ne 0) {
    Write-Log "FATAL: regeneration failed. Stopping -- do not run labelling steps against a bad artifact."
    exit 4
}
Write-Log "Regeneration complete."

# --- Step 5: deterministic verdicts + conservation ---------------------------
Write-Log "STEP 5/10: deterministic verdicts on $GenId (conservation runs at 7b, after the judge pass) ..."
& $Python -m evals deterministic-verdicts `
    --transcript "$GenDir\outputs.jsonl" `
    --json-out "$GenDir\deterministic_judged.jsonl" 2>&1 | ForEach-Object { Write-Log $_ }
if ($LASTEXITCODE -ne 0) { Write-Log "FATAL: deterministic-verdicts failed."; exit 4 }

# --- Step 6: label survival against the NEW transcript (read-only) -----------
# This is the empirical answer to "do I need to relabel". DEC-181 made drift criteria-only,
# so a regeneration should not drift anything by construction -- verify, do not assume.
Write-Log "STEP 6/10: label survival against the new transcript (READ-ONLY; never writes labels_v1.jsonl) ..."
$SurvivalLog = Join-Path $StampDir "label_survival_postregen_$Stamp.log"
& $Python "scripts\check_label_survival.py" --transcript "$GenDir\outputs.jsonl" *>&1 | Tee-Object -FilePath $SurvivalLog
Write-Log "check_label_survival.py exit $LASTEXITCODE (output: $SurvivalLog). Expect 393 survive / 0 drift / 0 orphaned."

# --- Step 7: panel judge the NEW arm (~4h) (B3) ------------------------------
# Arm 1 is measured on the SAME instrument as k3_73e6c36, so the two are on one ruler and
# compare.py's judge-identity gate (ISSUE-185) will not refuse a future comparison.
Write-Log "STEP 7/10: panel judge over the NEW arm $GenId (~4h) ..."
$P2Out = Join-Path $StampDir "arm1_panel_$Stamp.stdout.log"
$P2Err = Join-Path $StampDir "arm1_panel_$Stamp.stderr.log"
$p2Start = Get-Date
$proc2 = Start-Process -FilePath $Python -ArgumentList @(
    "-m", "evals", "judge",
    "--transcript", "$GenDir\outputs.jsonl",
    "--reports", "evals\reports",
    "--json-out", "$GenDir\judged.jsonl",
    "--panel"
) -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -Wait `
  -RedirectStandardOutput $P2Out -RedirectStandardError $P2Err
$P2Duration = New-TimeSpan -Start $p2Start -End (Get-Date)
$Arm1Status = Read-RunStatus (Join-Path $GenDir "run_status.json")
Write-Log ("Arm 1 panel finished in {0:hh\:mm\:ss}, exit {1}." -f $P2Duration, $proc2.ExitCode)
if (Test-MeasurementValid $Arm1Status) {
    Write-Log "Arm 1 measurement VALID (status=$($Arm1Status.status)) kappa=$($Arm1Status.fleiss_kappa) agreement=$($Arm1Status.raw_agreement) cases=$($Arm1Status.cases_passed)/$($Arm1Status.cases_total)"
} else {
    Write-Log "Arm 1 measurement INVALID -- EVAL-P22.1 below will refuse to build a partial ordering. See $P2Err."
}

# --- Step 7b: conservation, now that BOTH verdict sources exist --------------
# verdict_sources.load_unified_rows silently skips a missing file, so running this
# before the judge pass would have checked conservation over the deterministic rows
# only and reported a clean result from half the corpus. Ordered here deliberately.
Write-Log "STEP 7b: check_conservation over the complete verdict set ..."
$ConservationLog = Join-Path $StampDir "conservation_$Stamp.log"
& $Python "scripts\check_conservation.py" --gen-dir $GenDir *>&1 | Tee-Object -FilePath $ConservationLog
Write-Log "check_conservation.py exit $LASTEXITCODE (output: $ConservationLog). Non-zero is a finding to review, not automatically fatal."

# --- Step 8: EVAL-P22.1 label order + EVAL-P22.2 oracle dry run --------------
Write-Log "STEP 8/10: EVAL-P22.1 labelling order (--require-both) and EVAL-P22.2 oracle dry-run ..."
$OrderLog = Join-Path $StampDir "label_order_$Stamp.log"
$OrderPrefix = Join-Path $RepoRoot "evals\calibration\label_order_$GenId"
& $Python "scripts\build_label_order.py" $GenDir $OrderPrefix --require-both *>&1 | Tee-Object -FilePath $OrderLog
$OrderExit = $LASTEXITCODE
Write-Log "build_label_order.py exit $OrderExit (output: $OrderLog). Non-zero means a verdict source was missing -- the ordering was NOT written, on purpose."

$Scorers = @(
    @{ Name = "refusal_judge"; TP = 60; FP = 8; FN = 4; TN = 3 },
    @{ Name = "tone_judge"; TP = 100; FP = 10; FN = 4; TN = 3 },
    @{ Name = "affirms_judge"; TP = 100; FP = 10; FN = 2; TN = 1 },
    @{ Name = "keyword_any"; TP = 15; FP = 3; FN = 2; TN = 1 },
    @{ Name = "anti_hallucination_grounded"; TP = 30; FP = 5; FN = 5; TN = 3 }
)
$OracleLog = Join-Path $StampDir "oracle_p22_2_$Stamp.log"
foreach ($s in $Scorers) {
    Write-Log "  -- $($s.Name): tp=$($s.TP) fp=$($s.FP) fn=$($s.FN) tn=$($s.TN)"
    & make mock-calibrate-oracle GEN_ID=$GenId SCORER=$($s.Name) TP=$($s.TP) FP=$($s.FP) FN=$($s.FN) TN=$($s.TN) *>&1 |
        Tee-Object -FilePath $OracleLog -Append
}
Write-Log "Oracle dry-run complete (output: $OracleLog)."

# --- Steps 9-10: EVAL-P22B (the engine A/B track) ----------------------------
$trend = @{ Exit = -1; Rows = 0; Kappa = $null }
$harnessExit = -1
if ($Through -ge 9) {
    $trend = Invoke-TrendBaseline -GenId $GenId -GenDir $GenDir -StampDir $StampDir
} else {
    Write-Log "STEP 9/10: SKIPPED (-Through $Through)."
}
if ($Through -ge 10) {
    $fp = Invoke-FalsePositiveCheck -StampDir $StampDir
    $harnessExit = $fp.Exit
} else {
    Write-Log "STEP 10/10: SKIPPED (-Through $Through). Re-enter later with:"
    Write-Log "  powershell -NoProfile -ExecutionPolicy Bypass -File project-harness\Run-OvernightCombined.ps1 -IUnderstand -ResumeGenId $GenId"
}

# --- Handoff -----------------------------------------------------------------
$TotalDuration = New-TimeSpan -Start $RunStart -End (Get-Date)
$Handoff = Join-Path $RepoRoot "project-harness\MORNING_HANDOFF_COMBINED.md"
$P1Line = if (Test-MeasurementValid $P1Status) {
    "kappa **$($P1Status.fleiss_kappa)**, agreement $($P1Status.raw_agreement), $($P1Status.cases_passed)/$($P1Status.cases_total) cases (status $($P1Status.status))"
} else { "**INVALID** -- see ``$P1Err``" }
$A1Line = if (Test-MeasurementValid $Arm1Status) {
    "kappa **$($Arm1Status.fleiss_kappa)**, agreement $($Arm1Status.raw_agreement), $($Arm1Status.cases_passed)/$($Arm1Status.cases_total) cases (status $($Arm1Status.status))"
} else { "**INVALID** -- see ``$P2Err``" }
$TrendLine = if ($trend.Exit -eq 0) {
    "``evals/trend/trend_v1.jsonl`` now holds **$($trend.Rows)** row(s); this arm's fleiss_kappa = **$($trend.Kappa)**"
} elseif ($trend.Exit -eq -1) { "SKIPPED (-Through)" } else { "**FAILED** (exit $($trend.Exit)) -- no usable baseline row" }
$HarnessLine = switch ($harnessExit) {
    0  { "**PASS** — an unchanged engine read as no-regression. The gate does not fire on noise, so later verdicts mean something." }
    1  { "**FAIL** — the gate fired on an UNCHANGED engine. Its threshold is wrong; every later verdict is noise until fixed. NOT an engine regression." }
    2  { "**SETUP ERROR** — a precondition failed or no comparable baseline existed. Nothing was measured." }
    3  { "**INSTRUMENT DEGRADED** — inter-judge agreement fell. Expected with refusal_judge at kappa 0.225 (ISSUE-184). Investigate the panel, not the engine." }
    -1 { "SKIPPED (-Through)" }
    default { "unknown exit $harnessExit" }
}

@"
# Overnight combined run — handoff

Finished: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Total duration: $("{0:hh\:mm\:ss}" -f $TotalDuration)
Commit under test: **$Sha**
New A/B arm: **$GenId**
Full log: ``$LogFile``

## Results

| Step | Outcome |
|---|---|
| Phase 1 panel (k3_73e6c36) | $P1Line |
| Regeneration #1 | wrote ``$GenDir`` |
| Label survival (post-regen) | see ``$SurvivalLog`` — expect 393 survive / 0 drift / 0 orphaned |
| Arm 1 panel ($GenId) | $A1Line |
| EVAL-P22.1 labelling order | exit $OrderExit — see ``$OrderLog`` |
| EVAL-P22.2 oracle dry-run | see ``$OracleLog`` |
| EVAL-P22B.1 trend baseline | $TrendLine |
| EVAL-P22B.2 false-positive check | $HarnessLine |

## What to check, in order

1. **Phase 1 reproduction.** Compare its kappa against the re-derived baseline
   (kappa 0.526, agreement 0.956, 329/345). Judge sampling is non-deterministic and
   qwen2.5:14b flipped on 9/115 records across repeats, so expect small drift, not an exact
   match. A kappa well inside [0.227, 0.730] is a pass; a large move is itself a finding.
2. **Label survival.** If anything drifted or was orphaned, a case was renamed or removed —
   that is the only mechanism that can orphan a label under DEC-181's criteria-only policy.
3. **Oracle kappas.** Confirm the five values match DEC-185's closed forms: refusal_judge=0.247,
   tone_judge=0.241, affirms_judge=0.106, keyword_any=0.146, anti_hallucination_grounded=0.232.
   This closes HUMAN GATE H9. The script does not judge this for you.
4. **Coverage gaps.** Read ``$($OrderPrefix).coverage_gaps.txt`` — every scorer listed there has
   zero rows of one verdict and cannot have that class measured however much you label.

## What you now have that you did not before

``$GenId`` is your **first valid A/B arm**: seeded, ``harness_version``-stamped, generated after
the ISSUE-165 tick unification, and panel-judged. ``k3_73e6c36`` cannot serve this role — its
``harness_version`` and ``seed`` are both null, so ``compare.py`` refuses it against any modern
run (ISSUE-186). Its value is as a labelled calibration corpus, not a baseline.

To A/B an engine change from here: change engine/agent/context code (which does NOT alter
``harness_version`` — that hashes cases, judge prompts and matchers.py), regenerate to a new
gen_id, panel-judge it, then:

``````
python -m evals compare evals\generations\$GenId evals\generations\<new_arm>
``````

Keep the instrument identical between arms. ``compare.py`` now refuses a panel-vs-single-judge
pairing (ISSUE-185, fixed 2026-08-18), but it cannot protect you from a roster change you make
deliberately.

## Not run, by design

- **EVAL-P22.3 (Opus pre-labelling)** — a paid, human-run session using
  ``evals/calibration/OPUS_LABEL_PROMPT.md``, deliberately outside any automated pipeline.
- Nothing wrote to ``evals/calibration/labels_v1.jsonl``. Every labelling step above is
  read-only or writes to the oracle-only path.

## Tick these by hand after reviewing

``EVAL-P20.4``, ``EVAL-P22.1``, ``EVAL-P22.2``, ``EVAL-P22B.1`` in ROADMAP.md, naming this gen_id.
Tick ``EVAL-P22B.2`` **only if the false-positive check above exited 0** — an exit 1 means the
gate's threshold is wrong, and an exit 3 means the instrument moved; neither is a passed no-op check.
``EVAL-P21.1``/``P21.2`` remain blocked on ISSUE-183 (their named acceptance clauses were never
exercised by a live run) — that is a wording call, not a re-run.

## EVAL-P22B.3 — the dependency re-point (do this LAST, and only after a green step 10)

Editing ``EVAL-P23``'s ``Depends on:`` line before step 10 has actually passed would assert a
prerequisite that is not yet true, which is exactly the flag EVAL-P22B.3 carries. When it is green:

1. In ``EVAL-P23``'s **Depends on:** line, replace ``EVAL-P22.4`` with ``EVAL-P22B.2``.
2. Record in ``EVAL-P23``'s Notes that the trend baseline is regeneration #1, not #2 — the
   publication track can re-baseline onto regeneration #2 later without invalidating any engine
   comparison made in between, because ``harness_version`` comparability governs, not run recency.
3. Drop ``EVAL-P23.1``/``.2``/``.3`` from ``HUMAN GATE H10``'s **Blocks:** list.

Effect: ``EVAL-P23`` no longer transitively depends on an Opus spend, and engine iteration is
unblocked independently of the publication-credibility track.
"@ | Set-Content -Path $Handoff -Encoding utf8

Write-Log "Wrote handoff: $Handoff"
Write-CloseoutChecklist -GenId $GenId -HarnessExit $harnessExit
Write-Log ("=== Combined overnight run complete in {0:hh\:mm\:ss} ===" -f $TotalDuration)
exit $(if ($harnessExit -gt 0) { $harnessExit } else { 0 })
