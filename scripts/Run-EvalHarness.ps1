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
        1 = ran clean, regression_gate fired
        2 = a precondition failed before anything was generated

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

.PARAMETER AllowNoBaseline
    Exit 0 instead of 2 when the trend store has no prior row to gate
    against - expected on the very first recorded run.

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
    "7. Compare vs the prior generation (make eval-compare)"
    "8. Record trend row + gate on regression (scripts/record_trend_and_gate.py)"
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

Write-Output "[7/8] Comparing against the prior generation (informational -- trend gate is authoritative)..."
& make eval-compare "BEFORE=k3_73e6c36" "AFTER=$GenId"
# compare's own exit code is not gating here -- regression_gate (step 8) is the
# authoritative verdict, computed from the trend store rather than a single pair.

Write-Output "[8/8] Recording trend row and gating on regression..."
$pythonArgs = @(
    "scripts/record_trend_and_gate.py",
    "--gen-id", $GenId,
    "--gen-dir", $GenDir
)
if ($AllowNoBaseline) { $pythonArgs += "--allow-no-baseline" }
& python @pythonArgs
$gateExit = $LASTEXITCODE

if ($gateExit -eq 0) {
    Write-Output "`nRun-EvalHarness: PASS (gen_id=$GenId)"
} elseif ($gateExit -eq 1) {
    Write-Output "`nRun-EvalHarness: REGRESSION (gen_id=$GenId) -- see regression_gate output above"
} else {
    Write-Output "`nRun-EvalHarness: SETUP ERROR (gen_id=$GenId, exit=$gateExit)"
}
exit $gateExit
