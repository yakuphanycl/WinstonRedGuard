param(
  [string]$App = "",
  [switch]$All
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "_lib.ps1")

# Apps that are intentionally NOT release-packaged yet
$SKIP_APPS = @(
"pc_motor"
  "shorts_engine"
)

function WRG-ToLower([string]$s) {
  if ($null -eq $s) { return "" }
  return $s.ToLowerInvariant()
}

function WRG-IsSkippedApp([string]$appName) {
  $n = WRG-ToLower $appName
  foreach ($s in $SKIP_APPS) {
    if ((WRG-ToLower $s) -eq $n) { return $true }
  }
  return $false
}

function WRG-ListApps([string]$appsRoot) {
  WRG-AssertPath $appsRoot "apps root"
  Get-ChildItem -LiteralPath $appsRoot -Directory |
    ForEach-Object { $_.Name } |
    Sort-Object
}

function WRG-AppRoot([string]$repoRoot, [string]$appName) {
  return (Join-Path $repoRoot ("apps\" + $appName))
}


function WRG-RunReleaseCheckForApp([string]$appName, [string]$appRoot) {
  WRG-AssertPath $appRoot "app root"
  WRG-PushDir $appRoot

  $tmp = $null
  try {
    $python = WRG-GetPython

    # Clean dist/
    $dist = Join-Path $appRoot "dist"
    if (Test-Path -LiteralPath $dist) { Remove-Item -Recurse -Force -LiteralPath $dist }

    WRG-RunDirect "build wheel" @($python, "-m", "build", "--wheel") @(0)
    $wheel = WRG-FindWheel $dist

    # Create temp venv
    $tmp = WRG-NewTempDir "wrg_release_"
    $venvDir = Join-Path $tmp "venv"
    WRG-RunDirect "create venv" @($python, "-m", "venv", $venvDir) @(0)

    $venvPy = Join-Path $venvDir "Scripts\python.exe"
    $pipBase = @($venvPy, "-m", "pip")

    WRG-RunDirect "pip bootstrap" ($pipBase + @("install","-q","-U","pip","setuptools","wheel")) @(0)
    WRG-RunDirect "pip install wheel" ($pipBase + @("install","-q",$wheel)) @(0)

    # Smoke import (package name = appName varsayımı)
    $code = "import importlib; importlib.import_module('$appName'); print('IMPORT_OK')"
    WRG-RunDirect "smoke import" @($venvPy, "-c", $code) @(0)
    # Optional: pytest if tests/ exists
    $testsDir = Join-Path $appRoot "tests"
# --- WRG: pytest (installed wheel must win) ---
# Defensive: testsDir must be non-null and absolute
$testsDir = $null
try { $testsDir = Join-Path $appRoot "tests" } catch { $testsDir = $null }

if (-not [string]::IsNullOrWhiteSpace($testsDir) -and (Test-Path -LiteralPath $testsDir -PathType Container)) {

  # Ensure pytest exists (release_check venv)
  try { & $venvPy -m pip install -q pytest | Out-Null } catch { & $venvPy -m pip install pytest }

  # Sanity: import from installed wheel
  try {
    WRG-RunDirect "import-check" @(
      $venvPy, "-c",
      "import workspace_inspector as p; import workspace_inspector.cli as c; print('OK', getattr(p,'__version__','no-version'), c.format_size_binary(2048))"
    ) @(0)
  } catch {
    WRG-Warn "Import-check failed; continuing to pytest anyway."
  }

  # Run pytest from temp dir so repo sources don't shadow installed wheel
  WRG-PushDir $tmp
  try {
    $testsAbs = (Resolve-Path -LiteralPath $testsDir).Path
    WRG-RunDirect "pytest" @($venvPy, "-m", "pytest", "-q", $testsAbs) @(0)
  } finally {
    WRG-PopDir
  }

} else {
  WRG-Warn "No tests/ directory; skipping pytest."
}
# --- /WRG: pytest ---WRG-Ok "$appName release check PASS"
  }
  finally {
    WRG-PopDir
    if ($tmp) { WRG-RemoveDirSafe $tmp }
  }
}
# --- main ---
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..") | Select-Object -ExpandProperty Path
$appsRoot = Join-Path $repoRoot "apps"

# If a single app is requested and it is intentionally skipped, exit cleanly
if (-not [string]::IsNullOrWhiteSpace($App)) {
  if (WRG-IsSkippedApp $App) {
    Write-Host ("[SKIP] {0} is intentionally not release-packaged yet." -f $App)
    exit 0
  }
}

if ($PSBoundParameters.ContainsKey('All') -or [string]::IsNullOrWhiteSpace($App)) {
  WRG-Info "Running for ALL apps under $appsRoot"

  $apps = WRG-ListApps $appsRoot
  $apps = $apps | Where-Object { -not (WRG-IsSkippedApp $_) }

  foreach ($appName in $apps) {
    WRG-Info "==> $appName"
    $appRoot = WRG-AppRoot $repoRoot $appName
    WRG-RunReleaseCheckForApp $appName $appRoot
  }

  exit 0
}

# Single app path (non-skipped)
$appName = $App
$appRoot = WRG-AppRoot $repoRoot $appName
WRG-RunReleaseCheckForApp $appName $appRoot
exit 0







