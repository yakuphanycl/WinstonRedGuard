# --- WRG: log controls ---
function WRG-Log {
  param([string]$Msg)
  if (-not $Quiet) { Write-Host $Msg }
}
function WRG-LogV {
  param([string]$Msg)
  if ($VerboseLog) { Write-Host $Msg }
}
function WRG-LogErr {
  param([string]$Msg)
  Write-Host $Msg -ForegroundColor Red
}
# Run a command; hide stdout/stderr unless -VerboseLog
function WRG-Run {
  param(
    [Parameter(Mandatory=$true)][string]$Title,
    [Parameter(Mandatory=$true)][string[]]$Cmd,
    [int[]]$OkExitCodes = @(0)
  )
  WRG-LogV ("[INFO] {0}" -f $Title)
  WRG-LogV ("==> {0}" -f ($Cmd -join ' '))

  if ($VerboseLog) {
    & $Cmd[0] @($Cmd[1..($Cmd.Count-1)])
    $rc = $LASTEXITCODE
  } else {
    $out = & $Cmd[0] @($Cmd[1..($Cmd.Count-1)]) 2>&1
    $rc = $LASTEXITCODE
  }

  if ($OkExitCodes -notcontains $rc) {
    WRG-LogErr ("[ERR] {0} (rc={1})" -f $Title, $rc)
    if (-not $VerboseLog) {
      # sadece fail olunca captured output'u bas
      $out | ForEach-Object { Write-Host $_ }
    }
    exit $rc
  }
}
# --- /WRG: log controls ---
param(
  [string]$App = "",
  [switch]$All,
  [switch]$VerboseLog,
  [switch]$Quiet
)Set-StrictMode -Version Latest
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
  if (Test-Path -LiteralPath $dist) {
    try {
      Remove-Item -Recurse -Force -LiteralPath $dist -ErrorAction Stop
    } catch {
      $q = "$dist._locked_$(Get-Date -Format yyyyMMdd_HHmmss)"
      try {
        Rename-Item -LiteralPath $dist -NewName (Split-Path $q -Leaf) -ErrorAction Stop
        Write-Host "[WARN] dist was locked; renamed to $(Split-Path $q -Leaf)"
      } catch {
        Write-Host "[WARN] dist locked and rename failed: $($_.Exception.Message)"
      }
      if (-not (Test-Path -LiteralPath $dist)) {
        New-Item -ItemType Directory -Path $dist | Out-Null
      }
    }
  }
    WRG-Run "build wheel" @($python, "-m", "build", "--wheel") @(0)
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
    WRG-Run "smoke import" @($venvPy, "-c", $code) @(0)
    # Optional: pytest if tests/ exists
$testsDir = Join-Path $appRoot "tests"

# --- WRG: pytest (installed wheel must win) ---
if (-not [string]::IsNullOrWhiteSpace($testsDir) -and (Test-Path -LiteralPath $testsDir -PathType Container)) {

  # Ensure pytest exists (release_check venv)
  try { & $venvPy -m pip install -q pytest | Out-Null } catch { & $venvPy -m pip install pytest }

  # Sanity: import from installed wheel (wheel-only venv)
  $importCmd = "import importlib; importlib.import_module('$appName'); print('OK')"
  try {
    WRG-Run "import-check" @($venvPy, "-c", $importCmd) @(0)
  } catch {
    WRG-Warn "Import-check failed for $appName; continuing to pytest anyway."
  }

  # Run pytest from temp dir so repo sources don't shadow installed wheel
  WRG-PushDir $tmp
  try {
    $testsAbs = (Resolve-Path -LiteralPath $testsDir).Path
    WRG-Run "pytest" @($venvPy, "-m", "pytest", "-q", $testsAbs) @(0)
  } finally {
    WRG-PopDir
  }

} else {
  WRG-Warn "No tests/ directory; skipping pytest."
}
# --- /WRG: pytest ---
WRG-Ok "$appName release check PASS"
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

# --- WRG: README apps index gate (contract) ---
$gen = Join-Path $PSScriptRoot "gen_apps_index.ps1"
if (Test-Path -LiteralPath $gen) {

  Write-Host "[INFO] README apps index gate"
  & pwsh -NoProfile -ExecutionPolicy Bypass -File $gen | Out-Host

  # If README changed, fail the release check (contract drift)
  & git diff --quiet -- "README.md"
  if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERR] README.md apps index is out of date (or line endings/encoding drift). Run tools/gen_apps_index.ps1 and commit README.md."
    exit 2
  }

} else {
  Write-Host "[WARN] tools/gen_apps_index.ps1 not found; skipping README gate."
}
# --- /WRG: README apps index gate ---


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






