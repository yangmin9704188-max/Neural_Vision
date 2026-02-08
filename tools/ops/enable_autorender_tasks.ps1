<#
.SYNOPSIS
  Re-enables Windows Scheduled Tasks previously disabled by disable_autorender_tasks.ps1.
  Rollback / symmetry counterpart.

.PARAMETER Execute
  If present, actually enables tasks. Without -Execute, runs in dry-run mode (default).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools/ops/enable_autorender_tasks.ps1
  powershell -ExecutionPolicy Bypass -File tools/ops/enable_autorender_tasks.ps1 -Execute
#>
param(
    [switch]$Execute
)
$DryRun = -not $Execute

$ErrorActionPreference = "Continue"

# ── Patterns (same as find script) ───────────────────────────────────
$patterns = @(
    "Neural_Vision",
    "ops_refresh.ps1",
    "smoke_status.ps1",
    "render_status.py",
    "run_ops_loop.py",
    "run_end_ops_hook.py",
    "autorender_tick.py"
)

# ── Scan ─────────────────────────────────────────────────────────────
$allTasks = @()
try {
    $allTasks = Get-ScheduledTask -ErrorAction SilentlyContinue
} catch {
    Write-Host "ENABLE_AUTORENDER: ERROR — Get-ScheduledTask failed: $_"
    exit 1
}

$candidates = @()
foreach ($task in $allTasks) {
    $actionStr = ""
    try {
        foreach ($a in $task.Actions) {
            $exe = if ($a.Execute) { $a.Execute } else { "" }
            $arg = if ($a.Arguments) { $a.Arguments } else { "" }
            $actionStr += "$exe $arg "
        }
    } catch { continue }

    foreach ($pat in $patterns) {
        if ($actionStr -match [regex]::Escape($pat)) {
            $candidates += $task
            break
        }
    }
}

if ($candidates.Count -eq 0) {
    Write-Host "ENABLE_AUTORENDER: 0 candidate tasks found. Nothing to enable."
    exit 0
}

Write-Host "ENABLE_AUTORENDER: $($candidates.Count) candidate task(s) found."
if ($DryRun) {
    Write-Host "[DRY RUN] No changes will be made. Use -Execute to enable."
}
Write-Host ""

foreach ($task in $candidates) {
    $name = $task.TaskName
    $path = $task.TaskPath
    $state = $task.State.ToString()

    if ($DryRun) {
        Write-Host "  [DRY RUN] Would enable: ${path}${name} (current state: ${state})"
    } else {
        try {
            Enable-ScheduledTask -TaskName $name -TaskPath $path -ErrorAction Stop | Out-Null
            $updated = Get-ScheduledTask -TaskName $name -TaskPath $path -ErrorAction SilentlyContinue
            $newState = if ($updated) { $updated.State.ToString() } else { "UNKNOWN" }
            Write-Host "  [ENABLED] ${path}${name}: ${state} -> ${newState}"
        } catch {
            Write-Host "  [ERROR] ${path}${name}: $_"
        }
    }
}

Write-Host ""
Write-Host "Done."
exit 0
