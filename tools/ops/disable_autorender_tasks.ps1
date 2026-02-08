<#
.SYNOPSIS
  Disables Windows Scheduled Tasks identified by find_autorender_tasks.ps1.

.DESCRIPTION
  Runs find_autorender_tasks.ps1 to discover candidate tasks, then disables
  each one via Disable-ScheduledTask. DryRun mode is ON by default.

.PARAMETER Execute
  If present, actually disables tasks. Without -Execute, runs in dry-run mode (default).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools/ops/disable_autorender_tasks.ps1
  powershell -ExecutionPolicy Bypass -File tools/ops/disable_autorender_tasks.ps1 -Execute
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
    Write-Host "DISABLE_AUTORENDER: ERROR — Get-ScheduledTask failed: $_"
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
    Write-Host "DISABLE_AUTORENDER: 0 candidate tasks found. Nothing to disable."
    exit 0
}

Write-Host "DISABLE_AUTORENDER: $($candidates.Count) candidate task(s) found."
if ($DryRun) {
    Write-Host "[DRY RUN] No changes will be made. Use -Execute to disable."
}
Write-Host ""

foreach ($task in $candidates) {
    $name = $task.TaskName
    $path = $task.TaskPath
    $state = $task.State.ToString()

    if ($DryRun) {
        Write-Host "  [DRY RUN] Would disable: ${path}${name} (current state: ${state})"
    } else {
        try {
            Disable-ScheduledTask -TaskName $name -TaskPath $path -ErrorAction Stop | Out-Null
            # Re-read state
            $updated = Get-ScheduledTask -TaskName $name -TaskPath $path -ErrorAction SilentlyContinue
            $newState = if ($updated) { $updated.State.ToString() } else { "UNKNOWN" }
            Write-Host "  [DISABLED] ${path}${name}: ${state} -> ${newState}"
        } catch {
            Write-Host "  [ERROR] ${path}${name}: $_"
        }
    }
}

Write-Host ""
Write-Host "Done."
exit 0
