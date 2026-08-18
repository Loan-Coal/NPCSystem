<#
.SYNOPSIS
    Single entry point for the eval harness (EVAL-P23.3): preflight -> generate ->
    panel judge -> deterministic verdicts -> score -> calibrate -> compare vs
    baseline -> record trend -> gate.

.DESCRIPTION
    Supersedes project-harness/scripts/run_eval_k3.ps1 (a self-declared TEMPORARY
    one-off with no preflight, no exit-code verdict, and no trend row). This
    script's exit code IS its verdict:
        0 = ran clean, no regression
        1 = ran clean, regression_gate fired (the ENGINE regressed)
        2 = a precondition failed before anything was generated, or there was
            no comparable baseline to gate against
        3 = the INSTRUMENT degraded: inter-judge agreement fell, so this run's
            rate comparison is not trustworthy and the engine is not
            necessarily at fault (EVAL-P23 Defect E). Distinct from 1 on
            purpose - with refusal_judge at kappa 0.225 (ISSUE-184) this fires
            in practice, and debugging the engine over it wastes the session.

    Preflight must fail loudly: every silently-worthless artifact in this
    project's history came from a precondition that was false and unchecked
    (see project-harness/ROADMAP.md Program 3). Nothing is generated until
    every precondition passes.

.PARAMETER DryRun
    Print the planned steps and exit 0 without checking any precondition or
    running anything. ISSUE-126 is the standing reminder that a --dry-run
    which hangs or partially executes is worse than none - this one always
    terminates immediately after printing the plan.

.PARAMETER K
    Repetitions per case for the generation pass. Default 3.

.PARAMETER GenId
    Generation id for this run. Default "k<K>_<short git sha>".

.PARAMETER BaseUrl
    Engine base URL for the preflight health/world checks. Default
    http://localhost:8000.

.PARAMETER Baseline
    gen_id of the trend row to compare and gate against. Defaults to whatever
    the gate would pick on its own: the most recent trend row sharing this run's
    harness_version (scripts/record_trend_and_gate.py --print-baseline). Steps 7
    and 8 are always given the SAME baseline - before EVAL-P23's Defect A fix,
    step 7 compared against a hardcoded gen_id while step 8 gated against the
    trend store, so the informational delta table and the authoritative verdict
    described different comparisons. When no comparable baseline exists, step 7
    is skipped with an explicit message rather than silently.

.PARAMETER AllowNoBaseline
    Exit 0 instead of 2 when the trend store holds no COMPARABLE prior row to
    gate against - expected on the very first recorded run, and after a
    harness_version change (a case, judge-prompt or matcher edit) has made every
    stored row incomparable.

.EXAMPLE
    powershell scripts/Run-EvalHarness.ps1 -DryRun
.EXAMPLE
    powershell scripts/Run-EvalHarness.ps1 -K 3
#>

[CmdletBinding()]
param(
    [switch]$DryRun,
    [int]$K = 3,
    [string]$GenId = "",
    [string]$BaseUrl = "http://localhost:8000",
    [string]$Baseline = "",
    [switch]$AllowNoBaseline
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

$Plan = @(
    "1. Preflight: engine reachable, ollama panel models present, eval worlds seeded, tree clean"
    "2. Generate (make eval-generate, k=$K)"
    "3. Panel judge (make eval-judge, --panel: mixtral:8x7b + qwen2.5:14b + llama3.1:8b)"
    "4. Deterministic verdicts (make eval-deterministic-verdicts)"
    "5. Score / report (make eval-score)"
    "6. Calibrate (make eval-calibrate)"
    "7. Resolve the baseline (latest trend row sharing this run's harness_version, or -Baseline),"
    "   then compare candidate vs that baseline -- skipped, loudly, when there is none"
    "8. Record trend row + gate on regression against the SAME baseline (scripts/record_trend_and_gate.py)"
    "   exit codes: 0 clean / 1 engine regression / 2 setup or no comparable baseline / 3 instrument degraded"
)

if ($DryRun) {
    Write-Output "Run-EvalHarness.ps1 plan (-DryRun -- nothing executed, no precondition checked):"
    foreach ($step in $Plan) { Write-Output "  $step" }
    exit 0
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

function Test-EnginePrecondition {
    param([string]$Name, [scriptblock]$Check)
    Write-Output "Preflight: $Name ..."
    $ok = $false
    try { $ok = & $Check } catch { $ok = $false }
    if (-not $ok) {
        Write-Output "Preflight FAILED: $Name"
        # -ErrorAction Continue overrides the script-level $ErrorActionPreference =
        # "Stop": Write-Error would otherwise throw a terminating exception here,
        # which skips the explicit `exit 2` below and makes powershell.exe's own
        # uncaught-exception exit code (1) win instead -- indistinguishable from
        # exit 1 (ran clean, regression fired). The precondition-failure and
        # regression exit codes must stay distinct; see this script's own
        # .DESCRIPTION for the exit-code contract.
        Write-Error "Precondition failed: $Name. Nothing was generated." -ErrorAction Continue
        exit 2
    }
    Write-Output "Preflight OK: $Name"
}

Test-EnginePrecondition "engine reachable ($BaseUrl/health)" {
    $resp = Invoke-WebRequest -Uri "$BaseUrl/health" -TimeoutSec 5 -UseBasicParsing
    return $resp.StatusCode -eq 200
}

Test-EnginePrecondition "ollama panel models present (mixtral:8x7b, qwen2.5:14b, llama3.1:8b)" {
    $models = (& ollama list 2>$null) -join "`n"
    return ($models -match "mixtral:8x7b") -and ($models -match "qwen2\.5:14b") -and ($models -match "llama3\.1:8b")
}

Test-EnginePrecondition "eval worlds seeded (demo + village + tavern representative NPCs)" {
    $apiKey = $env:API_KEY_SECRET
    $headers = @{}
    if ($apiKey) { $headers["X-API-Key"] = $apiKey }
    foreach ($npcId in @("mira_innkeeper", "vw_elder", "tw_innkeeper")) {
        $resp = Invoke-WebRequest -Uri "$BaseUrl/v1/npc/$npcId/state" -TimeoutSec 5 -UseBasicParsing -Headers $headers
        if ($resp.StatusCode -ne 200) { return $false }
    }
    return $true
}

Test-EnginePrecondition "working tree clean" {
    $status = git status --porcelain
    return [string]::IsNullOrWhiteSpace($status)
}

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if (-not $GenId) {
    $sha = (git rev-parse --short HEAD).Trim()
    $GenId = "k${K}_${sha}"
}
$GenDir = "evals/generations/$GenId"
$Transcript = "$GenDir/outputs.jsonl"

Write-Output ""
Write-Output "All preflight checks passed. gen_id=$GenId"
Write-Output ""

Write-Output "[2/8] Generating (k=$K)..."
& make eval-generate "ARGS=--k $K --gen-id $GenId"
if ($LASTEXITCODE -ne 0) { Write-Error "generate failed"; exit $LASTEXITCODE }

Write-Output "[3/8] Panel judging..."
& make eval-judge "TRANSCRIPT=$Transcript" "GEN_ID=$GenId" "ARGS=--panel"
if ($LASTEXITCODE -ne 0) { Write-Error "panel judge failed"; exit $LASTEXITCODE }

Write-Output "[4/8] Deterministic verdicts..."
& make eval-deterministic-verdicts "TRANSCRIPT=$Transcript" "GEN_ID=$GenId"
if ($LASTEXITCODE -ne 0) { Write-Error "deterministic verdicts failed"; exit $LASTEXITCODE }

Write-Output "[5/8] Scoring..."
& make eval-score "TRANSCRIPT=$Transcript"
if ($LASTEXITCODE -ne 0) { Write-Error "score failed"; exit $LASTEXITCODE }

Write-Output "[6/8] Calibrating..."
& make eval-calibrate
if ($LASTEXITCODE -ne 0) { Write-Error "calibrate failed"; exit $LASTEXITCODE }

Write-Output "[7/8] Resolving the baseline this run is comparable with..."
if (-not $Baseline) {
    $resolved = & python scripts/record_trend_and_gate.py --gen-id $GenId --gen-dir $GenDir --print-baseline
    if ($LASTEXITCODE -ne 0) { Write-Error "baseline resolution failed"; exit 2 }
    if ($resolved) { $Baseline = ($resolved | Select-Object -Last 1).Trim() }
}

if ($Baseline) {
    Write-Output "[7/8] Comparing $Baseline -> $GenId (informational; step 8 gates on this SAME pair)..."
    & make eval-compare "BEFORE=$Baseline" "AFTER=$GenId"
    # compare's own exit code is not gating here -- regression_gate (step 8) is the
    # authoritative verdict. Both now describe the same pair: before EVAL-P23's
    # Defect A fix this step compared against a hardcoded gen_id that could never
    # compare at all (ISSUE-186), so it was permanently inert.
} else {
    Write-Output "[7/8] SKIPPED: no trend row shares this run's harness_version, so there is nothing comparable to compare against. Step 8 reports the same and will not gate."
}

Write-Output "[8/8] Recording trend row and gating on regression..."
$pythonArgs = @(
    "scripts/record_trend_and_gate.py",
    "--gen-id", $GenId,
    "--gen-dir", $GenDir
)
if ($Baseline) { $pythonArgs += @("--baseline-gen-id", $Baseline) }
if ($AllowNoBaseline) { $pythonArgs += "--allow-no-baseline" }
& python @pythonArgs
$gateExit = $LASTEXITCODE

if ($gateExit -eq 0) {
    Write-Output "`nRun-EvalHarness: PASS (gen_id=$GenId, baseline=$Baseline)"
} elseif ($gateExit -eq 1) {
    Write-Output "`nRun-EvalHarness: ENGINE REGRESSION (gen_id=$GenId, baseline=$Baseline) -- see regression_gate output above"
} elseif ($gateExit -eq 3) {
    Write-Output "`nRun-EvalHarness: INSTRUMENT DEGRADED (gen_id=$GenId, baseline=$Baseline) -- inter-judge agreement fell, so the rate comparison above is not trustworthy and the engine is not necessarily at fault. Investigate the judge panel, not the engine."
} else {
    Write-Output "`nRun-EvalHarness: SETUP ERROR (gen_id=$GenId, exit=$gateExit)"
}
exit $gateExit
