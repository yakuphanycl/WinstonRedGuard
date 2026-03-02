Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "YY-FE GOLDEN: start" -ForegroundColor Cyan
Write-Host ("PWD: " + (Get-Location))

if (-not $env:VIRTUAL_ENV) {
  Write-Host "WARN: venv not detected (VIRTUAL_ENV empty). Continue anyway." -ForegroundColor Yellow
}

Write-Host "Running: python -m pytest -q" -ForegroundColor Cyan
python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "YY-FE GOLDEN: PASS" -ForegroundColor Green
exit 0