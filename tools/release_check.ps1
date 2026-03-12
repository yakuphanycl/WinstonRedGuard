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

function WRG-HasPackagingManifest([string]$appRoot) {
  if ([string]::IsNullOrWhiteSpace($appRoot)) { return $false }

  return (Test-Path -LiteralPath (Join-Path $appRoot "pyproject.toml") -PathType Leaf) -or
    (Test-Path -LiteralPath (Join-Path $appRoot "setup.py") -PathType Leaf) -or
    (Test-Path -LiteralPath (Join-Path $appRoot "setup.cfg") -PathType Leaf)
}

function WRG-GetAppList([string]$appsRoot) {
  WRG-AssertPath $appsRoot "apps root"
  Get-ChildItem -LiteralPath $appsRoot -Directory |
    Where-Object { WRG-HasPackagingManifest $_.FullName } |
    ForEach-Object { $_.Name } |
    Sort-Object
}

function WRG-AppRoot([string]$repoRoot, [string]$appName) {
  return (Join-Path (Join-Path $repoRoot "apps") $appName)
}

function WRG-ResolveImportTarget([string]$appRoot, [string]$appName) {
  $srcRoot = Join-Path $appRoot "src"
  if (-not (Test-Path -LiteralPath $srcRoot -PathType Container)) {
    return $null
  }

  if (-not [string]::IsNullOrWhiteSpace($appName)) {
    if (Test-Path -LiteralPath (Join-Path $srcRoot $appName) -PathType Container) {
      return $appName
    }

    if (Test-Path -LiteralPath (Join-Path $srcRoot ($appName + ".py")) -PathType Leaf) {
      return $appName
    }
  }

  $packageDirs = @(Get-ChildItem -LiteralPath $srcRoot -Directory -ErrorAction SilentlyContinue |
      Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "__init__.py") -PathType Leaf } |
      Sort-Object Name)
  if ($packageDirs.Count -eq 1) {
    return $packageDirs[0].Name
  }

  $modules = @(Get-ChildItem -LiteralPath $srcRoot -File -Filter *.py -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -ne "__init__.py" } |
      Sort-Object Name)
  if ($modules.Count -eq 1) {
    return [System.IO.Path]::GetFileNameWithoutExtension($modules[0].Name)
  }

  return $null
}

function WRG-ResolveInstalledImportTarget([string]$venvPy, [string]$appName, [string]$wheelPath) {
  $code = @'
import importlib.metadata as md
import os
import re
import sys

app_name = sys.argv[1]
wheel_path = sys.argv[2]

def normalize(value):
    return re.sub(r"[-_.]+", "-", value).lower()

def valid_import_name(value):
    return re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value) is not None

def emit_target(dist):
    top_level = dist.read_text("top_level.txt") or ""
    for line in top_level.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        if candidate.endswith((".dist-info", ".egg-info")):
            continue
        if "/" in candidate or "\\" in candidate:
            continue
        if valid_import_name(candidate):
            print(candidate)
            raise SystemExit(0)

    name = (dist.metadata.get("Name") or "").strip()
    fallback = name.replace("-", "_")
    if valid_import_name(fallback):
        print(fallback)
        raise SystemExit(0)

candidates = []
for value in (
    app_name,
    app_name.replace("-", "_"),
    app_name.replace("_", "-"),
):
    if value and value not in candidates:
        candidates.append(value)

wheel_name = os.path.basename(wheel_path)
match = re.match(r"^(?P<dist>.+?)-[^-]+-[^-]+-[^-]+-[^-]+\.whl$", wheel_name)
if match:
    dist_name = match.group("dist")
    for value in (
        dist_name,
        dist_name.replace("-", "_"),
        dist_name.replace("_", "-"),
    ):
        if value and value not in candidates:
            candidates.append(value)

candidate_norms = {normalize(value) for value in candidates if value}

for candidate in candidates:
    try:
        emit_target(md.distribution(candidate))
    except md.PackageNotFoundError:
        continue

for dist in md.distributions():
    name = (dist.metadata.get("Name") or "").strip()
    if name and normalize(name) in candidate_norms:
        emit_target(dist)

'@

  try {
    $result = WRG-RunDirect -FilePath $venvPy -CommandArgs @("-c", $code, $appName, $wheelPath) -Capture -Quiet
  }
  catch {
    WRG-Warn ("Installed metadata import target resolution failed: {0}" -f $_.Exception.Message)
    return $null
  }

  $lines = @($result.output | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  if ($lines.Count -gt 0) {
    return $lines[-1].Trim()
  }

  return $null
}

function WRG-InstallTestDependencies([string]$venvPy, [string]$appRoot) {
  $requirementsFile = $null
  foreach ($candidate in @(
      (Join-Path $appRoot "requirements-test.txt"),
      (Join-Path $appRoot "requirements-dev.txt"),
      (Join-Path (Join-Path $appRoot "tests") "requirements.txt")
    )) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
      $requirementsFile = $candidate
      break
    }
  }

  if ($requirementsFile) {
    WRG-Info ("Installing test dependencies from {0}" -f (Split-Path -Leaf $requirementsFile))
    try {
      WRG-RunDirect "pip install test requirements" @($venvPy, "-m", "pip", "install", "-q", "-r", $requirementsFile) @(0)
    }
    catch {
      WRG-RunDirect "pip install test requirements" @($venvPy, "-m", "pip", "install", "-r", $requirementsFile) @(0)
    }
    return
  }

  try {
    WRG-RunDirect "pip install pytest" @($venvPy, "-m", "pip", "install", "-q", "pytest") @(0)
  }
  catch {
    WRG-RunDirect "pip install pytest" @($venvPy, "-m", "pip", "install", "pytest") @(0)
  }
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
      Remove-Item -Recurse -Force -LiteralPath $dist
    }

    WRG-RunDirect "build wheel" @($python, "-m", "build", "--wheel") @(0)
    $wheel = WRG-FindWheel $dist

    # Create temp venv
    $tmp = WRG-NewTempDir "wrg_release_"
    $venvDir = Join-Path $tmp ".venv"
    WRG-RunDirect "create venv" @($python, "-m", "venv", $venvDir) @(0)

    $venvPy = Join-Path $venvDir "Scripts\python.exe"
    $pipBase = @($venvPy, "-m", "pip")

    WRG-RunDirect "pip bootstrap" ($pipBase + @("install", "-q", "-U", "pip", "setuptools", "wheel")) @(0)
    WRG-RunDirect "pip install wheel" ($pipBase + @("install", "-q", $wheel)) @(0)

    $importTarget = WRG-ResolveImportTarget $appRoot $appName
    if (-not $importTarget) {
      $importTarget = WRG-ResolveInstalledImportTarget $venvPy $appName $wheel
    }
    if ($importTarget) {
      $code = "import importlib; importlib.import_module('$importTarget'); print('IMPORT_OK')"
      WRG-RunDirect "smoke import" @($venvPy, "-c", $code) @(0)
    }
    else {
      WRG-Warn "Skipping smoke import; could not resolve import target from src/."
    }

    # Optional: pytest if tests/ exists
    $testsDir = $null
    try {
      $testsDir = Join-Path $appRoot "tests"
    }
    catch {
      $testsDir = $null
    }

    if (-not [string]::IsNullOrWhiteSpace($testsDir) -and (Test-Path -LiteralPath $testsDir -PathType Container)) {
      WRG-InstallTestDependencies $venvPy $appRoot

      # Copy runtime policy file if present (some tests/CLI expect cwd-relative policy.json)
      $policySrc = Join-Path $appRoot "policy.json"
      $policyDst = Join-Path $tmp "policy.json"

      if (Test-Path -LiteralPath $policySrc -PathType Leaf) {
        Copy-Item -LiteralPath $policySrc -Destination $policyDst -Force
      }

      # Run pytest from temp dir so repo sources don't shadow installed wheel
      WRG-PushDir $tmp
      try {
        $testsAbs = (Resolve-Path -LiteralPath $testsDir).Path
        WRG-RunDirect "pytest" @($venvPy, "-m", "pytest", "-q", $testsAbs) @(0)
      }
      finally {
        WRG-PopDir
      }
    }
    else {
      WRG-Warn "No tests/ directory; skipping pytest."
    }

    WRG-Ok "$appName release check PASS"
  }
  finally {
    WRG-PopDir
    if ($tmp) {
      WRG-RemoveDirSafe $tmp
    }
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

  $apps = WRG-GetAppList $appsRoot
  $apps = $apps | Where-Object { -not (WRG-IsSkippedApp $_) }
  $passedApps = @()
  $failedApps = @()

  foreach ($appName in $apps) {
    WRG-Info "==> $appName"
    $appRoot = WRG-AppRoot $repoRoot $appName
    try {
      WRG-RunReleaseCheckForApp $appName $appRoot
      $passedApps += $appName
    }
    catch {
      $message = $_.Exception.Message
      WRG-Warn ("{0} release check FAIL: {1}" -f $appName, $message)
      $failedApps += [pscustomobject]@{
        App = $appName
        Message = $message
      }
    }
  }

  WRG-Info "Release check summary:"
  if ($passedApps.Count -gt 0) {
    WRG-Ok ("Passed apps: {0}" -f ($passedApps -join ", "))
  }
  else {
    WRG-Warn "Passed apps: none"
  }

  if ($failedApps.Count -gt 0) {
    WRG-Warn ("Failed apps: {0}" -f (($failedApps | ForEach-Object { $_.App }) -join ", "))
    foreach ($failure in $failedApps) {
      WRG-Warn ("Failure detail [{0}]: {1}" -f $failure.App, $failure.Message)
    }
    exit 1
  }

  WRG-Ok "All packaged apps passed release checks."
  exit 0
}

# Single app path (non-skipped)
$appName = $App
$appRoot = WRG-AppRoot $repoRoot $appName

if (-not (Test-Path -LiteralPath $appRoot -PathType Container)) {
  throw "App not found: $appRoot"
}

if (-not (WRG-HasPackagingManifest $appRoot)) {
  throw ("App exists but is not a packaged Python app (missing pyproject.toml, setup.py, or setup.cfg): {0}" -f $appRoot)
}

WRG-RunReleaseCheckForApp $appName $appRoot
exit 0
