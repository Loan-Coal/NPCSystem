# TEMPORARY: one-off scheduled runner for k=3 eval pass (2026-08-07 6h delay request).
# Not part of the standard toolchain — delete once the run has been kicked off and
# confirmed, or promote into a permanent script if this becomes a recurring need.
$ErrorActionPreference = "Continue"

Set-Location "c:\Users\lohan\Documents\hackathons\NPCSystem"

$logDir = "project-harness\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "eval_k3_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

Start-Transcript -Path $logPath -Append

docker-compose up -d
$env:JUDGE_TIMEOUT_SECONDS = "300"
ollama run mixtral:8x7b "hi"

$GEN_ID = "k3_$(git rev-parse --short HEAD)"
make eval-generate "ARGS=--k 3 --gen-id $GEN_ID"
make eval-judge    "TRANSCRIPT=evals/generations/$GEN_ID/outputs.jsonl" "GEN_ID=$GEN_ID"
make eval-score    "TRANSCRIPT=evals/generations/$GEN_ID/outputs.jsonl"

Get-Content "evals/generations/$GEN_ID/meta.json"
(Get-Content "evals/generations/$GEN_ID/outputs.jsonl" | Measure-Object -Line).Lines
(Get-Content "evals/generations/$GEN_ID/judged.jsonl"  | Measure-Object -Line).Lines
Select-String -Path "evals/reports/*.md" -Pattern "binary_judge_infra_failure" | Measure-Object

Stop-Transcript
