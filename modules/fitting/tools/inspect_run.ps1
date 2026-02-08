# inspect_run.ps1
# Inspects fitting run output files and displays summary information

param(
    [Parameter(Mandatory = $true)]
    [string]$RunDir
)

$ErrorActionPreference = "Continue"

Write-Host "=== Inspecting Run Directory: $RunDir ==="
Write-Host ""

# Check if directory exists
if (-not (Test-Path $RunDir)) {
    Write-Host "[ERROR] Directory not found: $RunDir"
    exit 0
}

# Define file paths
$factsPath = Join-Path $RunDir "facts_summary.json"
$fittingPath = Join-Path $RunDir "fitting_summary.json"

# Read facts_summary.json
Write-Host "--- facts_summary.json ---"
if (Test-Path $factsPath) {
    try {
        $facts = Get-Content $factsPath -Raw -Encoding UTF8 | ConvertFrom-Json
        
        Write-Host "nan_rate: $($facts.nan_rate)"
        Write-Host "nan_count: total=$($facts.nan_count.total), nan=$($facts.nan_count.nan)"
        
        Write-Host ""
        Write-Host "reasons:"
        foreach ($key in $facts.reasons.PSObject.Properties.Name) {
            Write-Host "  $key : $($facts.reasons.$key)"
        }
        
        Write-Host ""
        Write-Host "warnings:"
        if ($facts.warnings -and $facts.warnings.PSObject.Properties.Count -gt 0) {
            foreach ($code in $facts.warnings.PSObject.Properties.Name) {
                $msgCount = $facts.warnings.$code.Count
                Write-Host "  $code : $msgCount messages"
            }
        }
        else {
            Write-Host "  (none)"
        }
    }
    catch {
        Write-Host "[ERROR] Failed to parse facts_summary.json: $_"
    }
}
else {
    Write-Host "[MISSING] facts_summary.json not found"
}

Write-Host ""

# Read fitting_summary.json
Write-Host "--- fitting_summary.json ---"
if (Test-Path $fittingPath) {
    try {
        $fitting = Get-Content $fittingPath -Raw -Encoding UTF8 | ConvertFrom-Json
        
        Write-Host "metrics:"
        foreach ($key in $fitting.metrics.PSObject.Properties.Name) {
            $value = $fitting.metrics.$key
            if ($null -eq $value) {
                Write-Host "  $key : null"
            }
            else {
                Write-Host "  $key : $value"
            }
        }
    }
    catch {
        Write-Host "[ERROR] Failed to parse fitting_summary.json: $_"
    }
}
else {
    Write-Host "[MISSING] fitting_summary.json not found"
}

Write-Host ""
Write-Host "=== Inspection Complete ==="
exit 0
