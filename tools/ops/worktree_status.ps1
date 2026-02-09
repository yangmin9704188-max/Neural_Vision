param(
  [string]$RepoRoot = "."
)

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path $RepoRoot).Path

Write-Output "RepoRoot: $resolvedRoot"
Write-Output ""

$paths = @()
$currentPath = $null

foreach ($line in (git -C $resolvedRoot worktree list --porcelain)) {
  if ($line -like "worktree *") {
    if ($currentPath) { $paths += $currentPath }
    $currentPath = $line.Substring(9)
  }
}
if ($currentPath) { $paths += $currentPath }

foreach ($path in $paths) {
  $branch = git -C $path rev-parse --abbrev-ref HEAD
  $statusLines = @(git -C $path status --porcelain)
  $statusCount = $statusLines.Count
  $statusSummary = if ($statusCount -eq 0) { "clean" } else { "$statusCount change(s)" }

  Write-Output "Path: $path"
  Write-Output "Branch: $($branch.Trim())"
  Write-Output "Status: $statusSummary"
  if ($statusCount -gt 0) {
    $statusLines | ForEach-Object { Write-Output "  $_" }
  }
  Write-Output ""
}
