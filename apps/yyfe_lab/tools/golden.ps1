Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "YY-FE GOLDEN: start" -ForegroundColor Cyan
Write-Host ("PWD: " + (Get-Location))

if (-not $env:VIRTUAL_ENV) {
# Honest venv detection: accept either activated venv (VIRTUAL_ENV) OR local .venv python
$appRoot = Split-Path -Parent $PSScriptRoot
$venvPy  = Join-Path $appRoot ".venv\Scripts\python.exe"

$hasVenv = $false
if ($env:VIRTUAL_ENV) { $hasVenv = $true }
elseif (Test-Path -LiteralPath $venvPy -PathType Leaf) { $hasVenv = $true }

if (-not $hasVenv) {
  Write-Host "WARN: venv not detected (VIRTUAL_ENV empty and .venv missing). Continue anyway." -ForegroundColor Yellow
}
}

# Pick a Python to run pytest:
#  - Prefer local .venv if present
#  - Otherwise fall back to `py -3`
$appRoot = Split-Path $PSScriptRoot -Parent
$venvPy  = Join-Path $appRoot ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath $venvPy -PathType Leaf) {
  $py = $venvPy
  Write-Host ("Running: {0} -m pytest -q" -f $py) -ForegroundColor Cyan
  & $py -m pytest -q
} else {
  Write-Host "Running: py -3 -m pytest -q" -ForegroundColor Cyan
  & py -3 -m pytest -q
}if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "YY-FE GOLDEN: PASS" -ForegroundColor Green
exit 0

exit $LASTEXITCODE

