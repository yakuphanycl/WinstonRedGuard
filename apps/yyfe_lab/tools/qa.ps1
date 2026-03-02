param(
  [switch]$SkipApply
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path ".").Path
$py   = Join-Path $root ".venv\Scripts\python.exe"
$yyfe = Join-Path $root ".venv\Scripts\yyfe.exe"

if (!(Test-Path $py))   { throw "python not found: $py" }
if (!(Test-Path $yyfe)) { throw "yyfe.exe not found: $yyfe" }

# --- Force local temp dirs (avoid WinError 5 on user TEMP)
$tmpBase = Join-Path $root ".tmp"
$tempDir = Join-Path $tmpBase "temp"
$pytestBase = Join-Path $tmpBase "pytest"

New-Item -ItemType Directory -Force $tempDir | Out-Null
New-Item -ItemType Directory -Force $pytestBase | Out-Null

$env:TEMP = $tempDir
$env:TMP  = $tempDir

Write-Host "QA: temp pinned to $tempDir" -ForegroundColor Cyan

# --- BOM gate
Write-Host "QA: check BOM" -ForegroundColor Cyan
& $py "tools\check_bom.py" | Out-Host
if ($LASTEXITCODE -ne 0) { throw "QA_FAIL: BOM found" }

# --- Tests
Write-Host "QA: pytest" -ForegroundColor Cyan
& $py -m pytest -q --basetemp $pytestBase | Out-Host
if ($LASTEXITCODE -ne 0) { throw "QA_FAIL: pytest failed" }

# --- Golden path
Write-Host "QA: golden plan->validate->apply" -ForegroundColor Cyan
& $yyfe plan --profile lab | Out-Host
if ($LASTEXITCODE -ne 0) { throw "QA_FAIL: plan failed" }

& $yyfe validate --plan "output\plan.json" | Out-Host
if ($LASTEXITCODE -ne 0) { throw "QA_FAIL: validate failed" }

if (-not $SkipApply) {
  & $yyfe apply --plan "output\plan.json" | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "QA_FAIL: apply failed" }
} else {
  Write-Host "QA: apply skipped" -ForegroundColor Yellow
}

Write-Host "QA_OK" -ForegroundColor Green
