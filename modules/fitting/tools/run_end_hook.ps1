# tools/run_end_hook.ps1
# Append run_finished event to exports/progress/PROGRESS_LOG.jsonl.
# Uses local progress_append.py (no main repo). Exit 0 on append, 1 on failure.
# REQUIRED: Set FITTING_STEP_ID (e.g. F06, F07) before calling. No default to prevent STEP_ID_MISSING.
$ErrorActionPreference = "Stop"

$labRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $env:FITTING_STEP_ID -or $env:FITTING_STEP_ID -notmatch '^F\d{2}$') {
    Write-Host "run_end_hook: FITTING_STEP_ID required (e.g. F06, F07). Set before calling to prevent STEP_ID_MISSING."
    Write-Host "  Example: `$env:FITTING_STEP_ID='F07'; .\tools\run_end_hook.ps1"
    exit 1
}
$stepId = $env:FITTING_STEP_ID
$done = if ($env:FITTING_DOD_DONE_DELTA -match '^\d+$') { [int]$env:FITTING_DOD_DONE_DELTA } else { 0 }
$total = if ($env:FITTING_DOD_TOTAL -match '^\d+$') { [int]$env:FITTING_DOD_TOTAL } else { $null }
$status = if ($env:FITTING_STATUS) { $env:FITTING_STATUS } else { "OK" }
$note = if ($env:FITTING_NOTE) { $env:FITTING_NOTE } else { "run end hook" }

$script = Join-Path $labRoot "tools\progress_append.py"
if (-not (Test-Path $script)) {
    Write-Host "run_end_hook: progress_append.py not found at $script"
    exit 1
}

$procArgs = @("--step", $stepId, "--done", $done, "--note", $note, "--event", "run_finished", "--status", $status)
if ($null -ne $total) { $procArgs += @("--total", $total) }

Set-Location $labRoot
& py $script @procArgs 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "run_end_hook: progress event appended (step=$stepId)"
exit 0
