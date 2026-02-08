# make_release_snapshot.ps1
# Creates a timestamped snapshot of fitting_lab v0 files before porting to main repo

$ErrorActionPreference = "Stop"

# Generate timestamp
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outDir = "releases/fitting_v0_$timestamp"

Write-Host "Creating release snapshot: $outDir"

# Create output directory
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

# Define source files to copy
$filesToCopy = @(
    @{Source = "labs/runners/run_fitting_v0_facts.py"; Dest = "run_fitting_v0_facts.py"},
    @{Source = "labs/specs/fitting_manifest.schema.json"; Dest = "fitting_manifest.schema.json"},
    @{Source = "contracts/fitting_interface_v0.md"; Dest = "fitting_interface_v0.md"}
)

$missingFiles = @()
$copiedFiles = @()

# Check and copy files
foreach ($file in $filesToCopy) {
    $sourcePath = $file.Source
    $destPath = Join-Path $outDir $file.Dest
    
    if (Test-Path $sourcePath) {
        Copy-Item -Path $sourcePath -Destination $destPath -Force
        $copiedFiles += $sourcePath
        Write-Host "[OK] Copied: $sourcePath -> $destPath"
    } else {
        $missingFiles += $sourcePath
        Write-Host "[MISSING] File not found: $sourcePath"
    }
}

# Summary
Write-Host ""
Write-Host "=== Release Snapshot Summary ==="
Write-Host "Output directory: $outDir"
Write-Host "Copied files: $($copiedFiles.Count)"
Write-Host "Missing files: $($missingFiles.Count)"

if ($missingFiles.Count -gt 0) {
    Write-Host ""
    Write-Host "Missing files:"
    foreach ($missing in $missingFiles) {
        Write-Host "  - $missing"
    }
}

Write-Host ""
Write-Host "Snapshot created successfully."
exit 0
