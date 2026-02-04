# tools/smoke_status.ps1
# Smoke test for render_status.py. Exit 0 always.
$ErrorActionPreference = "Continue"

$fitting = $env:FITTING_LAB_ROOT
$garment = $env:GARMENT_LAB_ROOT

if (-not $fitting -and -not $garment) {
    Write-Host "Hint: Set FITTING_LAB_ROOT and/or GARMENT_LAB_ROOT for full brief ingestion."
    Write-Host "  e.g. `$env:FITTING_LAB_ROOT='..\fitting_lab'; `$env:GARMENT_LAB_ROOT='..\garment_lab'"
    Write-Host ""
}

py tools/render_status.py
$r = $LASTEXITCODE

$diff = git diff -- ops/STATUS.md 2>$null
if ($diff) {
    Write-Host ""
    Write-Host "--- git diff ops/STATUS.md ---"
    $diff
}

exit 0
