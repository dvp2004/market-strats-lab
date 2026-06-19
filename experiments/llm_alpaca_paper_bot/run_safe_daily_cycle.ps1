param(
    [switch]$CandidatePreview
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "SAFE DAILY PAPER BOT CYCLE"
Write-Host "=========================="
Write-Host ""

$env:ENABLE_PAPER_ORDERS = "false"
$env:DRY_RUN = "true"

if ($CandidatePreview) {
    Write-Host "Running candidate-active preview config: QQQ_75_250_cross"
    $env:PAPER_BOT_CONFIG_PATH = "experiments\llm_alpaca_paper_bot\paper_bot_config_candidate_preview.yaml"
} else {
    Write-Host "Running default active config: QQQ_50_200_cross"
    Remove-Item Env:\PAPER_BOT_CONFIG_PATH -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "1. Parallel signal preview"
.\.venv\Scripts\python.exe experiments\llm_alpaca_paper_bot\ma_parallel_signal_preview.py

Write-Host ""
Write-Host "2. Config-driven paper signal safety check"
.\.venv\Scripts\python.exe experiments\llm_alpaca_paper_bot\config_driven_paper_signal.py

Write-Host ""
Write-Host "3. Daily paper status report"
.\.venv\Scripts\python.exe experiments\llm_alpaca_paper_bot\daily_paper_status_report.py

Write-Host ""
Write-Host "Cycle complete. No orders enabled."
Write-Host ""

Remove-Item Env:\PAPER_BOT_CONFIG_PATH -ErrorAction SilentlyContinue
