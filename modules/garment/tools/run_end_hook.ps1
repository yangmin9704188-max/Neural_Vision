# tools/run_end_hook.ps1
# Append run_finished event to exports/progress/PROGRESS_LOG.jsonl.
# Uses local progress_append.py (no main repo). Exit 0 on append, 1 on failure.
$ErrorActionPreference = "Stop"

$labRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $env:GARMENT_STEP_ID -or $env:GARMENT_STEP_ID -notmatch '^G\d{2}$') {
    Write-Host "run_end_hook: GARMENT_STEP_ID required (e.g. G06, G07). Set before calling to prevent STEP_ID_MISSING."
    Write-Host "  Example: `$env:GARMENT_STEP_ID='G07'; .\tools\run_end_hook.ps1"
    exit 1
}
$stepId = $env:GARMENT_STEP_ID
$done = if ($env:GARMENT_DOD_DONE_DELTA -match '^\d+$') { [int]$env:GARMENT_DOD_DONE_DELTA } else { 0 }
$total = if ($env:GARMENT_DOD_TOTAL -match '^\d+$') { [int]$env:GARMENT_DOD_TOTAL } else { $null }
$status = if ($env:GARMENT_STATUS) { $env:GARMENT_STATUS } else { "OK" }
$note = if ($env:GARMENT_NOTE) { $env:GARMENT_NOTE } else { "run end hook" }

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
