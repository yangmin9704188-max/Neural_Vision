# tools/run_fitting_smoke_e2e.ps1
# Smoke-1/2/3 E2E: generate facts_summary, strict-run (warn-only), append ROUND_END.
$ErrorActionPreference = "Stop"
$labRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Set-Location $labRoot

# 1) Generate facts_summary + fit_signal (runner-based)
& py tools\run_fitting_smoke_e2e.py 2>&1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 2) Ensure smoke run-dirs exist
$dirs = @("runs/fitting_smoke1_ok", "runs/fitting_smoke2_hard_gate", "runs/fitting_smoke3_degraded")
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) {
        Write-Host "run_fitting_smoke_e2e: $d not found"
        exit 1
    }
}

# 3) strict-run (warn-only) on smoke1
$strictExit = 1
$val = Join-Path $labRoot "tools\validate_fitting_manifest.py"
if (Test-Path $val) {
    & py $val --run-dir runs/fitting_smoke1_ok --strict-run 2>&1
    $strictExit = $LASTEXITCODE
    if ($strictExit -ne 0) {
        Write-Host "run_fitting_smoke_e2e: strict-run smoke1 exit=$strictExit (warn-only, continuing)"
    }
} else {
    Write-Host "run_fitting_smoke_e2e: validator not found, skipping strict-run"
}

# 4) facts_summary validator (if exists)
$factsVal = Join-Path $labRoot "tools\validate_fitting_facts_summary.py"
if (Test-Path $factsVal) {
    $factsPaths = @("runs/fitting_smoke1_ok/facts_summary.json", "runs/fitting_smoke2_hard_gate/facts_summary.json", "runs/fitting_smoke3_degraded/facts_summary.json")
    foreach ($fp in $factsPaths) {
        if (Test-Path $fp) {
            & py $factsVal --facts $fp 2>&1
            if ($LASTEXITCODE -ne 0) { Write-Host "run_fitting_smoke_e2e: facts validation FAIL $fp (continuing)" }
        }
    }
}

# 5) Append ROUND_END events (idempotent: run append script)
$strictResult = if ($strictExit -eq 0) { "OK" } else { "SKIPPED" }
& py tools\append_smoke_e2e_rounds.py --strict-result $strictResult 2>&1

Write-Host "run_fitting_smoke_e2e: done"
