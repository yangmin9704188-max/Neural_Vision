# tools/invoke_ops_hook.ps1
# 1) roundwrap end (active round 있으면) 2) run_end_ops_hook. step-id hard-required.
# Usage: .\invoke_ops_hook.ps1 <fitting_step_id> [garment_step_id] [main_repo_path]
# Example: .\invoke_ops_hook.ps1 F09
$ErrorActionPreference = "Stop"
if ($args.Count -lt 1 -or $args[0] -notmatch '^F\d{2}$') {
    Write-Host "Usage: .\invoke_ops_hook.ps1 <fitting_step_id> [garment_step_id] [main_repo_path]"
    exit 1
}
$fittingStep = $args[0]
$garmentStep = if ($args[1] -match '^G\d{2}$') { $args[1] } else { "G06" }
$labRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$mainRoot = if ($args[1] -match '^G\d{2}$' -and $args.Count -ge 3) { $args[2] } elseif ($args[1] -notmatch '^G\d{2}$' -and $args.Count -ge 2) { $args[1] } else { (Join-Path (Split-Path $labRoot) "Neural_Vision") }
# roundwrap end if active (ROUND_START 했으면 ROUND_END 자동)
$roundActive = Join-Path $labRoot "exports\progress\.round_active.json"
if (Test-Path $roundActive) {
    Set-Location $labRoot
    & py tools\roundwrap.py end --note "ops hook (step $fittingStep)" 2>&1 | Out-Null
}
$hookScript = Join-Path $mainRoot "tools\ops\run_end_ops_hook.py"
if (-not (Test-Path $hookScript)) {
    Write-Host "invoke_ops_hook: run_end_ops_hook.py not found at $hookScript"
    exit 1
}
$env:FITTING_STEP_ID = $fittingStep
$env:GARMENT_STEP_ID = $garmentStep
$env:FITTING_LAB_ROOT = $labRoot
if (-not $env:GARMENT_LAB_ROOT) {
    $env:GARMENT_LAB_ROOT = Join-Path (Split-Path $labRoot) "garment_lab"
}
Set-Location $mainRoot
& py $hookScript --require-step-id --fitting-step-id $fittingStep --garment-step-id $garmentStep
$exitCode = $LASTEXITCODE
Write-Host "invoke_ops_hook: done (fitting=$fittingStep, garment=$garmentStep, exit=$exitCode)"
exit $exitCode
