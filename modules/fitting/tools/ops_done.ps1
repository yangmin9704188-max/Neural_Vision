# tools/ops_done.ps1
# Append one progress event to PROGRESS_LOG.jsonl. Usage: .\ops_done.ps1 <step_id> <note>
# Example: .\ops_done.ps1 F05 "error code standardized"
$ErrorActionPreference = "Stop"
if ($args.Count -lt 2) {
    Write-Host "Usage: .\ops_done.ps1 <step_id> <note>"
    exit 1
}
$stepId = $args[0]
if ($stepId -notmatch '^[FG]\d{2}$') {
    Write-Host "ops_done: step_id must match Fxx or Gxx (e.g. F05, G06). Got: $stepId"
    exit 1
}
$note = $args[1..($args.Count - 1)] -join " "
$labRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$script = Join-Path $labRoot "tools\progress_append.py"
if (-not (Test-Path $script)) {
    Write-Host "ops_done: progress_append.py not found at $script"
    exit 1
}
Set-Location $labRoot
& py $script --step $stepId --done 0 --total 0 --note $note --event "note" --status "OK"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "ops_done: appended step=$stepId"
exit 0
