# Run Smoke-2 Garment Hard Gate Test

$ErrorActionPreference = "Stop"

# 1. Setup Paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot = Split-Path -Parent $ScriptDir
$FixturePath = Join-Path $RepoRoot "tests\fixtures\invalid_mesh.obj"
$ToolsDir = Join-Path $RepoRoot "tools"
$BundleTool = Join-Path $ToolsDir "garment_generate_bundle.py"
$ValidateTool = Join-Path $ToolsDir "validate_geometry_manifest.py"
$SchemaPath = Join-Path $RepoRoot "contracts\geometry_manifest.schema.json"

# Check if Schema exists, if not try sibling repo
if (-not (Test-Path $SchemaPath)) {
    # Try ../fitting_lab/contracts/geometry_manifest.schema.json
    $SiblingSchema = Join-Path (Split-Path -Parent $RepoRoot) "fitting_lab\contracts\geometry_manifest.schema.json"
    if (Test-Path $SiblingSchema) {
        $SchemaPath = $SiblingSchema
    }
    else {
        Write-Warning "Schema not found at $SchemaPath or $SiblingSchema. Validation might fail."
    }
}

# 2. Prepare Output Directory
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutDir = Join-Path $RepoRoot "runs\smoke\smoke2\$Timestamp"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "=== Garment Smoke-2: Hard Gate Reproduction ==="
Write-Host "Fixture: $FixturePath"
Write-Host "Output: $OutDir"

# 3. Detect Python
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $PyCmd = "py"
}
elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
    $PyCmd = "python"
}
else {
    Write-Error "Python not found (py or python)"
    exit 1
}

# 4. Run Bundle Generation (Expect Exit Code 1)
Write-Host "`n[Action] Running Bundle Generation..."
$BundleExitCode = 0
try {
    & $PyCmd $BundleTool --mesh $FixturePath --out_dir $OutDir --schema $SchemaPath
}
catch {
    # PowerShell throws on non-zero exit if ErrorAction is Stop?
    # Actually, direct execution of native commands doesn't always throw.
    # We check $LASTEXITCODE.
}
$BundleExitCode = $LASTEXITCODE

Write-Host "Bundle Exit Code: $BundleExitCode"

# Check Gate Logic (Expect 1 or non-zero)
if ($BundleExitCode -eq 0) {
    Write-Error "[FAIL] HARD_GATE: False (Exit code 0, expected non-zero for invalid mesh)"
    exit 1
}
else {
    Write-Host "[PASS] HARD_GATE: True (Exit code non-zero as expected)"
}

# 5. Verify Artifacts exist
$MetaPath = Join-Path $OutDir "garment_proxy_meta.json"
$ManifestPath = Join-Path $OutDir "geometry_manifest.json"

if (-not (Test-Path $MetaPath)) {
    Write-Error "[FAIL] OUTPUTS_PRESENT: garment_proxy_meta.json missing"
    exit 1
}
if (-not (Test-Path $ManifestPath)) {
    Write-Error "[FAIL] OUTPUTS_PRESENT: geometry_manifest.json missing"
    exit 1
}
Write-Host "[PASS] OUTPUTS_PRESENT: Both files exist"

# 6. Validate Manifest (Must PASS, Exit 0)
Write-Host "`n[Action] Validating Manifest..."
& $PyCmd $ValidateTool --manifest $ManifestPath --schema $SchemaPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "[FAIL] MANIFEST_VALIDATE: Failed (Exit code $LASTEXITCODE)"
    exit 1
}
Write-Host "[PASS] MANIFEST_VALIDATE: Success"

# 7. Progress append (G02: smoke2 gate run)
$RunEndHook = Join-Path $RepoRoot "tools\run_end_hook.ps1"
if (Test-Path $RunEndHook) {
    $env:GARMENT_STEP_ID = "G02"
    $env:GARMENT_NOTE = "smoke2 hard gate passed"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $RunEndHook 2>&1 | Out-Null
}

Write-Host "`n=== Smoke-2 PASSED ==="
exit 0
