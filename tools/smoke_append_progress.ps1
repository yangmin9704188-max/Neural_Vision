# tools/smoke_append_progress.ps1
# Smoke: append note event to fitting/garment PROGRESS_LOG. Exit 0 always.
$ErrorActionPreference = "Continue"

$rootsPath = "ops/lab_roots.local.json"
if (-not (Test-Path $rootsPath)) {
    Write-Host "Usage: Copy ops/lab_roots.local.json.example to ops/lab_roots.local.json"
    Write-Host "  Or set FITTING_LAB_ROOT, GARMENT_LAB_ROOT and run:"
    Write-Host "  py tools/ops/append_progress_event.py --lab-root <path> --module fitting --step-id F01 --event note --note 'smoke' --status OK"
    exit 0
}

$cfg = Get-Content $rootsPath -Raw | ConvertFrom-Json
$fitting = $cfg.FITTING_LAB_ROOT
$garment = $cfg.GARMENT_LAB_ROOT

if ($fitting) {
    py tools/ops/append_progress_event.py --lab-root $fitting --module fitting --step-id F01 --event note --note "smoke: progress event appended" --status OK
}
if ($garment) {
    py tools/ops/append_progress_event.py --lab-root $garment --module garment --step-id G01 --event note --note "smoke: progress event appended" --status OK
}

exit 0
