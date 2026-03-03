# Gate first: compile + schema + render smoke
try {
  pwsh -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\release_check.ps1" -Job ".\layer2\examples\min_job.json"
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} catch {
  Write-Host "ERROR: release gate failed: $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}
param(
  [string]$JobPath = "shorts_engine\layer2\examples\min_job.json"
)


# --- resolve JobPath relative to repo root (robust) ---
$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..") | Select-Object -ExpandProperty Path
if (-not [System.IO.Path]::IsPathRooted($JobPath)) {
  $JobPath = Join-Path $repoRoot $JobPath
}
$JobPath = Resolve-Path -LiteralPath $JobPath -ErrorAction Stop | Select-Object -ExpandProperty Path
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path) | Out-Null
Set-Location ..

if (!(Test-Path -LiteralPath $JobPath)) { throw "Job not found: $JobPath" }

python -m layer2.cli.render_job --job $JobPath --no-eta
exit $LASTEXITCODE





