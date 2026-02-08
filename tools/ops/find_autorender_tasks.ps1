<#
.SYNOPSIS
  Scans Windows Task Scheduler for tasks that reference Neural_Vision ops scripts.

.DESCRIPTION
  Collects any scheduled task whose Actions contain one of:
    Neural_Vision, ops_refresh.ps1, smoke_status.ps1,
    render_status.py, run_ops_loop.py, run_end_ops_hook.py, autorender_tick.py

  Outputs: TaskPath / TaskName / State / Actions (1-line)

.PARAMETER OutLocalJson
  Save results to a local JSON file (default: ops/local/autorender_tasks.local.json).
  Set to "" to skip file output.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools/ops/find_autorender_tasks.ps1
  powershell -ExecutionPolicy Bypass -File tools/ops/find_autorender_tasks.ps1 -OutLocalJson ""
#>
param(
    [string]$OutLocalJson = "ops/local/autorender_tasks.local.json"
)

$ErrorActionPreference = "Continue"

# ── Patterns to match in task actions ────────────────────────────────
$patterns = @(
    "Neural_Vision",
    "ops_refresh.ps1",
    "smoke_status.ps1",
    "render_status.py",
    "run_ops_loop.py",
    "run_end_ops_hook.py",
    "autorender_tick.py"
)

# ── Scan all scheduled tasks ─────────────────────────────────────────
$allTasks = @()
try {
    $allTasks = Get-ScheduledTask -ErrorAction SilentlyContinue
} catch {
    Write-Host "FIND_AUTORENDER: ERROR — Get-ScheduledTask failed: $_"
    exit 1
}

$candidates = @()
foreach ($task in $allTasks) {
    # Flatten all actions into a single string for matching
    $actionStr = ""
    try {
        $actions = $task.Actions
        foreach ($a in $actions) {
            $exe = if ($a.Execute) { $a.Execute } else { "" }
            $arg = if ($a.Arguments) { $a.Arguments } else { "" }
            $actionStr += "$exe $arg "
        }
    } catch {
        continue
    }

    foreach ($pat in $patterns) {
        if ($actionStr -match [regex]::Escape($pat)) {
            $candidates += [PSCustomObject]@{
                TaskPath = $task.TaskPath
                TaskName = $task.TaskName
                State    = $task.State.ToString()
                Actions  = $actionStr.Trim()
            }
            break  # avoid duplicates for same task
        }
    }
}

# ── Output ───────────────────────────────────────────────────────────
if ($candidates.Count -eq 0) {
    Write-Host "FIND_AUTORENDER: 0 candidate tasks found."
} else {
    Write-Host "FIND_AUTORENDER: $($candidates.Count) candidate task(s) found."
    Write-Host ""
    foreach ($c in $candidates) {
        Write-Host "  TaskPath : $($c.TaskPath)"
        Write-Host "  TaskName : $($c.TaskName)"
        Write-Host "  State    : $($c.State)"
        Write-Host "  Actions  : $($c.Actions)"
        Write-Host ""
    }
}

# ── Save to local JSON (gitignored) ─────────────────────────────────
if ($OutLocalJson -ne "") {
    $repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
    # Resolve relative to repo root if not absolute
    if (-not [System.IO.Path]::IsPathRooted($OutLocalJson)) {
        $outPath = Join-Path $repoRoot $OutLocalJson
    } else {
        $outPath = $OutLocalJson
    }

    # Ensure parent dir exists
    $outDir = Split-Path -Parent $outPath
    if (-not (Test-Path $outDir)) {
        New-Item -ItemType Directory -Path $outDir -Force | Out-Null
    }

    $jsonData = $candidates | ForEach-Object {
        @{
            TaskPath = $_.TaskPath
            TaskName = $_.TaskName
            State    = $_.State
            Actions  = $_.Actions
        }
    }
    $jsonData | ConvertTo-Json -Depth 5 | Set-Content -Path $outPath -Encoding UTF8
    Write-Host "Saved to: $outPath"
}

exit 0
