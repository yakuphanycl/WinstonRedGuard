param(
  [string]$App = "",
  [switch]$All,
  [switch]$VerboseLog,
  [switch]$Quiet,
  [switch]$Help
)

$ErrorActionPreference = "Stop"

function RC-Info([string]$m){ if(-not $Quiet){ Write-Host "[INFO] $m" } }
function RC-Warn([string]$m){ if(-not $Quiet){ Write-Host "[WARN] $m" } }
function RC-Err([string]$m){ Write-Host "[ERR]  $m" }

function RC-Die([string]$m, [int]$code=1){
  RC-Err $m
  exit $code
}

function RC-HasCmd([string]$name){
  return $null -ne (Get-Command $name -ErrorAction SilentlyContinue)
}

function RC-CanRunPython([string]$cmd, [string[]]$prefix=@()){
  try {
    & $cmd @prefix "-c" "import sys; print(sys.executable)"
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

function RC-PickPython {
  if ((RC-HasCmd "python") -and (RC-CanRunPython "python")) { return "python" }
  if ((RC-HasCmd "python3") -and (RC-CanRunPython "python3")) { return "python3" }
  if ((RC-HasCmd "py") -and (RC-CanRunPython "py" @("-3"))) { return "py" }
  RC-Die "No working Python found on PATH (tried python, python3, py -3)." 2
}

function RC-RunDirect([string]$label, [string[]]$argv, [int[]]$ok=@(0)){
  if($VerboseLog){ RC-Info ("==> {0}`n    {1}" -f $label, ($argv -join " ")) }
  & $argv[0] @($argv[1..($argv.Count-1)])
  $rc = $LASTEXITCODE
  if($ok -notcontains $rc){
    RC-Die ("Command failed (rc={0}): {1}" -f $rc, ($argv -join " ")) $rc
  }
}

function RC-ListApps([string]$appsRoot){
  if(-not (Test-Path -LiteralPath $appsRoot -PathType Container)){ return @() }
  $dirs = Get-ChildItem -LiteralPath $appsRoot -Directory -ErrorAction SilentlyContinue
  return @($dirs | ForEach-Object { $_.Name })
}

function RC-MakeTempDir([string]$prefix){
  $base = [System.IO.Path]::GetTempPath()
  $name = "{0}_{1}" -f $prefix, ([guid]::NewGuid().ToString("N").Substring(0,8))
  $dir  = Join-Path $base $name
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  return $dir
}

function RC-Abs([string]$p){
  return (Resolve-Path -LiteralPath $p).Path
}

if($Help -or ((-not $All) -and [string]::IsNullOrWhiteSpace($App))){
@"
Usage:
  pwsh -File tools/release_check.ps1 -All
  pwsh -File tools/release_check.ps1 -App <app_name>

Options:
  -VerboseLog   print command lines
  -Quiet        less output
  -Help         show this message
"@ | Write-Host
  exit 0
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$appsRoot = Join-Path $repoRoot "apps"

# Apps that are intentionally NOT release-packaged yet
$SKIP_APPS = @()
$python = RC-PickPython
$pyVerArg = @()
if($python -eq "py"){ $pyVerArg = @("-3") }

# apps selection
$apps = @()
if($All -or [string]::IsNullOrWhiteSpace($App)){
  $apps = RC-ListApps $appsRoot
  RC-Info ("Running for ALL apps under {0}" -f $appsRoot)
} else {
  $apps = @($App)
  RC-Info ("Running for ONE app: {0}" -f $App)
}

# Only apply skip filter when -App is NOT provided
if([string]::IsNullOrWhiteSpace($App)){
  # Filter out skip apps (case-insensitive)
  $skipSet = @{}
  foreach($s in $SKIP_APPS){ $skipSet[$s.ToLowerInvariant()] = $true }
  $apps = @($apps | Where-Object { -not $skipSet.ContainsKey($_.ToLowerInvariant()) })
}

if(@($apps).Count -le 0){
  RC-Die "No apps found under apps/ (or filtered by SKIP_APPS)." 2
}

foreach($appName in $apps){
  $appRoot = Join-Path $appsRoot $appName
  if(-not (Test-Path -LiteralPath $appRoot -PathType Container)){
    RC-Die ("App not found: {0}" -f $appRoot) 2
  }

  RC-Info "==> $appName"

  $pyproject = Join-Path $appRoot "pyproject.toml"
  if(-not (Test-Path -LiteralPath $pyproject)){
    RC-Die ("Missing pyproject.toml in {0}" -f $appRoot) 2
  }

  Push-Location $appRoot
  try {
    # Clean dist/ so we never pick an old wheel
    $dist = Join-Path $appRoot "dist"
    if(Test-Path -LiteralPath $dist -PathType Container){
      try {
        Remove-Item -Recurse -Force -LiteralPath $dist -ErrorAction Stop
      } catch {
        # best-effort: don't fail release check just because dist is locked
        Remove-Item -Recurse -Force -LiteralPath $dist -ErrorAction SilentlyContinue
      }
    }
    # Ensure 'build' module is available for python -m build
    try {
      RC-RunDirect "ensure build" (@($python) + $pyVerArg + @("-m","pip","install","-q","build")) @(0)
    } catch {
      RC-RunDirect "ensure build (retry)" (@($python) + $pyVerArg + @("-m","pip","install","build")) @(0)
    }
    # Build wheel
    RC-RunDirect "build wheel" (@($python) + $pyVerArg + @("-m","build","--wheel")) @(0)

    # Find newest wheel in dist/
    $dist = Join-Path $appRoot "dist"
    if(-not (Test-Path -LiteralPath $dist -PathType Container)){
      RC-Die "dist/ missing after build" 3
    }
    $wheel = Get-ChildItem -LiteralPath $dist -Filter "*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if($null -eq $wheel){
      RC-Die "No wheel found in dist/" 3
    }
    RC-Info ("Testing wheel: {0}" -f $wheel.Name)

    # Create temp venv and install wheel
    $tmpDir = RC-MakeTempDir ("wrg_release_{0}" -f $appName)
    $venvDir = Join-Path $tmpDir ".venv"
    RC-RunDirect "create venv" (@($python) + $pyVerArg + @("-m","venv",$venvDir)) @(0)

    $venvPy = Join-Path $venvDir "Scripts\python.exe"
    if(-not (Test-Path -LiteralPath $venvPy)){
      RC-Die ("venv python not found: {0}" -f $venvPy) 4
    }

    RC-RunDirect "pip upgrade" @($venvPy,"-m","pip","install","-q","--upgrade","pip") @(0)

    RC-RunDirect "install wheel" @($venvPy,"-m","pip","install","-q",$wheel.FullName) @(0)

    # Run pytest if tests/ exists
    $testsDir = Join-Path $appRoot "tests"
    if(Test-Path -LiteralPath $testsDir -PathType Container){
      RC-RunDirect "ensure pytest" @($venvPy,"-m","pip","install","-q","pytest") @(0)

      # Contract: run pytest from temp dir so repo sources don't shadow installed wheel
      $pytestCache = Join-Path $tmpDir ".pytest_cache"
      Push-Location $tmpDir
      try {
        RC-RunDirect "pytest" @($venvPy,"-m","pytest","-q","-o","cache_dir=$pytestCache",(RC-Abs $testsDir)) @(0)
      } finally {
        Pop-Location
      }
    } else {
      RC-Warn "No tests/ directory; skipping pytest."
    }

  } finally {
    Pop-Location
  }
}

RC-Info "OK"
exit 0





