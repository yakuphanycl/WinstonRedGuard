param(
  [string]$App = "",
  [switch]$All
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "_lib.ps1")

function WRG-ListApps([string]$appsRoot) {
  WRG-AssertPath $appsRoot "apps root"
  Get-ChildItem -LiteralPath $appsRoot -Directory | ForEach-Object { $_.Name } | Sort-Object
}

function WRG-AppRoot([string]$repoRoot, [string]$appName) {
  return (Join-Path $repoRoot ("apps\" + $appName))
}

function WRG-CleanDist([string]$appRoot) {
  $dist = Join-Path $appRoot "dist"
  if (Test-Path -LiteralPath $dist) { Remove-Item -Recurse -Force -LiteralPath $dist }
}

function WRG-BuildWheel([string]$python, [string]$appRoot) {
  WRG-CleanDist $appRoot
  WRG-RunDirect "build wheel" @($python, "-m", "build", "--wheel") @(0)
  WRG-Ok "wheel build complete"
}

function WRG-MakeVenv([string]$python, [string]$venvDir) {
  WRG-RunDirect "create venv" @($python, "-m", "venv", $venvDir) @(0)
  $venvPy = Join-Path $venvDir "Scripts\python.exe"
  WRG-AssertPath $venvPy "venv python"
  WRG-RunDirect "pip upgrade" @($venvPy, "-m", "pip", "install", "--upgrade", "pip") @(0)
  return $venvPy
}

function WRG-InstallWheel([string]$venvPy, [string]$wheelPath) {
  WRG-RunDirect "install wheel" @($venvPy, "-m", "pip", "install", $wheelPath) @(0)
  WRG-Ok "installed"
}

function WRG-DetectModuleMain([string]$appRoot, [string]$appName) {
  # Prefer common patterns in this ecosystem:
  $candidates = @(
    "$appName.cli.main",
    "$appName.cli:main",
    "$appName.__main__",
    "$appName.main"
  )

  # If src/<name>/cli/main.py exists, strongest signal:
  $p1 = Join-Path $appRoot ("src\" + $appName + "\cli\main.py")
  if (Test-Path -LiteralPath $p1) { return "$appName.cli.main" }

  # Try __main__.py
  $p2 = Join-Path $appRoot ("src\" + $appName + "\__main__.py")
  if (Test-Path -LiteralPath $p2) { return "$appName.__main__" }

  # Fallback: first candidate
  return $candidates[0]
}

function WRG-SmokeHelp([string]$venvPy, [string]$moduleMain) {
  # python -m <module> --help
  # Prefer running package root if it has __main__.py (avoid runpy quirks; standard CLI)
  $appRoot = $PWD.Path
  $pkgRoot = $moduleMain.Split(".")[0]

  $main1 = Join-Path $appRoot (Join-Path $pkgRoot "__main__.py")
  $main2 = Join-Path $appRoot (Join-Path ("src\{0}" -f $pkgRoot) "__main__.py")

  $smokeModule = $moduleMain
  if ( (Test-Path -LiteralPath $main1 -PathType Leaf) -or (Test-Path -LiteralPath $main2 -PathType Leaf) ) {
    $smokeModule = $pkgRoot
  }

  Write-Host "[INFO] smokeModule=$smokeModule"
WRG-RunDirect "smoke --help" @($venvPy, "-m", $smokeModule, "--help") @(0)
}

function WRG-SmokeVersionJson([string]$venvPy, [string]$moduleMain) {
  # Best-effort: if "version" exists and returns JSON, validate it
  $out = & $venvPy -m $moduleMain version 2>$null
  $rc = $LASTEXITCODE
  if ($rc -eq 0 -and $out -and $out.TrimStart().StartsWith("{")) {
    WRG-AssertJson $out "version json"
  } else {
    WRG-Warn "version smoke skipped or non-JSON (rc=$rc). OK for tools without 'version'."
  }
}

function WRG-RunAppContractTests([string]$appRoot) {
  $appTests = Join-Path $appRoot "tools\contract_tests.ps1"
  if (Test-Path -LiteralPath $appTests) {
    WRG-RunDirect "app contract_tests.ps1" @("pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $appTests) @(0)
  } else {
    WRG-Warn "no app-level tools/contract_tests.ps1 found (skipping)"
  }
}

function WRG-CheckOneApp([string]$repoRoot, [string]$appName) {
  Write-Host ""
  Write-Host "===============================" -ForegroundColor DarkCyan
  Write-Host " WRG RELEASE CHECK :: $appName" -ForegroundColor DarkCyan
  Write-Host "===============================" -ForegroundColor DarkCyan

  $python = WRG-GetPython
  $appRoot = WRG-AppRoot $repoRoot $appName
  $pyproject = Join-Path $appRoot "pyproject.toml"

  WRG-AssertPath $appRoot "app root"
  WRG-AssertPath $pyproject "pyproject.toml"

  WRG-PushDir $appRoot
  $tmp = ""
  try {
    WRG-BuildWheel $python $appRoot
    $wheel = WRG-FindWheel (Join-Path $appRoot "dist")

    $tmp = WRG-NewTempDir "wrg-venv"
    $venvDir = Join-Path $tmp "venv"
    $venvPy = WRG-MakeVenv $python $venvDir
    WRG-InstallWheel $venvPy $wheel

    $moduleMain = WRG-DetectModuleMain $appRoot $appName
    WRG-Info "moduleMain=$moduleMain"

    WRG-SmokeHelp $venvPy $moduleMain
    WRG-SmokeVersionJson $venvPy $moduleMain
    WRG-RunAppContractTests $appRoot

    WRG-Ok "$appName release check PASS"
  } finally {
    WRG-PopDir
    if ($tmp) { WRG-RemoveDirSafe $tmp }
  }
}

# ---- main ----
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..") | Select-Object -ExpandProperty Path
$appsRoot = Join-Path $repoRoot "apps"

if ($All -or (-not $App)) {
  WRG-Info "Running for ALL apps under $appsRoot"
  $apps = WRG-ListApps $appsRoot
  if (-not $apps -or $apps.Count -eq 0) { WRG-Die "no apps found under $appsRoot" 1 }
  foreach ($a in $apps) { WRG-CheckOneApp $repoRoot $a }
} else {
  WRG-CheckOneApp $repoRoot $App
}

Write-Host ""
WRG-Ok "ALL CHECKS DONE"
exit 0





