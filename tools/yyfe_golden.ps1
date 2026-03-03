param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$appDir   = Join-Path $repoRoot "apps\yyfe_lab"

if (-not (Test-Path -LiteralPath $appDir -PathType Container)) {
  Write-Host "[FAIL] yyfe_lab not found: $appDir" -ForegroundColor Red
  exit 2
}

Push-Location $appDir
try {
  $env:PYTHONPATH = (Resolve-Path .\src).Path
  pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\golden.ps1
  exit $LASTEXITCODE
}
finally {
  Pop-Location
}

