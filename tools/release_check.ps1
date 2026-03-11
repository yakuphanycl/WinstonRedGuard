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

function RC-ReadJsonOrNull([string]$path){
  if(-not (Test-Path -LiteralPath $path -PathType Leaf)){ return $null }
  try {
    return (Get-Content -LiteralPath $path -Raw | ConvertFrom-Json -Depth 64)
  } catch {
    return $null
  }
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

$registryPath = Join-Path $repoRoot "apps\app_registry\data\registry.json"
$registryObj = RC-ReadJsonOrNull $registryPath
$appTypeByName = @{}
$registryApps = @()
if($null -ne $registryObj){
  if(($registryObj.PSObject.Properties.Name -contains "apps") -and ($null -ne $registryObj.apps)){
    $registryApps = @($registryObj.apps)
  } else {
    $registryApps = @($registryObj)
  }
}
foreach($entry in $registryApps){
  if($null -eq $entry){ continue }
  $entryName = [string]$entry.name
  if([string]::IsNullOrWhiteSpace($entryName)){ continue }
  $entryType = [string]$entry.app_type
  if([string]::IsNullOrWhiteSpace($entryType)){ $entryType = "python_app" }
  $appTypeByName[$entryName.ToLowerInvariant()] = $entryType
}

foreach($appName in $apps){
  $appRoot = Join-Path $appsRoot $appName
  if(-not (Test-Path -LiteralPath $appRoot -PathType Container)){
    RC-Die ("App not found: {0}" -f $appRoot) 2
  }

  RC-Info "==> $appName"

  $appType = "python_app"
  $appKey = $appName.ToLowerInvariant()
  if($appTypeByName.ContainsKey($appKey)){
    $candidateType = [string]$appTypeByName[$appKey]
    if(-not [string]::IsNullOrWhiteSpace($candidateType)){
      $appType = $candidateType
    }
  }
  if($appType.ToLowerInvariant() -eq "node_app"){
    RC-Info ("Skipping Python wheel build for node app: {0}" -f $appName)
    continue
  }

  $pyproject = Join-Path $appRoot "pyproject.toml"
  if(-not (Test-Path -LiteralPath $pyproject)){
    RC-Die ("Missing pyproject.toml for python app in {0}" -f $appRoot) 2
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

# Global gate: combined pytest for app_registry + governance_check
$registryTests = Join-Path $repoRoot "apps\app_registry\tests"
$governanceTests = Join-Path $repoRoot "apps\governance_check\tests"
$combinedPytestTargets = @()
$missingCombinedTargets = @()
if(Test-Path -LiteralPath $registryTests -PathType Container){
  $combinedPytestTargets += (RC-Abs $registryTests)
} else {
  $missingCombinedTargets += "apps/app_registry/tests"
}
if(Test-Path -LiteralPath $governanceTests -PathType Container){
  $combinedPytestTargets += (RC-Abs $governanceTests)
} else {
  $missingCombinedTargets += "apps/governance_check/tests"
}
if($combinedPytestTargets.Count -gt 0){
  if($combinedPytestTargets.Count -eq 2){
    RC-Info "==> global quality gate: combined pytest (app_registry + governance_check)"
  } else {
    RC-Warn ("Combined pytest partial target mode; missing: {0}" -f ($missingCombinedTargets -join ", "))
    RC-Info ("==> global quality gate: combined pytest (existing target: {0})" -f $combinedPytestTargets[0])
  }
  RC-RunDirect "ensure pytest (global)" (@($python) + $pyVerArg + @("-m","pip","install","-q","pytest")) @(0)
  RC-RunDirect "pytest combined" ((@($python) + $pyVerArg + @("-m","pytest","-q")) + $combinedPytestTargets) @(0)
} else {
  RC-Warn ("Combined pytest target dirs missing; skipping app_registry+governance_check combined run. Missing: {0}" -f ($missingCombinedTargets -join ", "))
}

# Global gate: governance policy check
$governanceSrc = Join-Path $repoRoot "apps\governance_check\src"
$governanceCli = Join-Path $governanceSrc "governance_check\cli.py"
$governanceRc = 0
$policyPath = Join-Path $repoRoot "artifacts\policy_check.json"
$governancePath = Join-Path $repoRoot "artifacts\governance_check.json"
if(Test-Path -LiteralPath $governanceCli -PathType Leaf){
  $artifactsDir = Join-Path $repoRoot "artifacts"
  if(-not (Test-Path -LiteralPath $artifactsDir -PathType Container)){
    New-Item -ItemType Directory -Force -Path $artifactsDir | Out-Null
  }
  RC-Info ("==> global governance gate: {0}" -f $governancePath)
  $oldPyPath = $env:PYTHONPATH
  try {
    if([string]::IsNullOrWhiteSpace($oldPyPath)){
      $env:PYTHONPATH = $governanceSrc
    } else {
      $env:PYTHONPATH = "{0};{1}" -f $governanceSrc, $oldPyPath
    }
    Push-Location $repoRoot
    try {
      if($VerboseLog){ RC-Info ("==> governance check`n    {0}" -f ((@($python) + $pyVerArg + @("-m","governance_check.cli","check","--json-out",$governancePath)) -join " ")) }
      & $python @pyVerArg "-m" "governance_check.cli" "check" "--json-out" $governancePath
      $governanceRc = $LASTEXITCODE
      if($governanceRc -ne 0){
        RC-Warn ("governance check reported non-zero rc={0}" -f $governanceRc)
      }
    } finally {
      Pop-Location
    }
  } finally {
    if($null -eq $oldPyPath){
      Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
      $env:PYTHONPATH = $oldPyPath
    }
  }
} else {
  RC-Warn "governance_check CLI not found; skipping governance gate."
}

# Aggregate health artifacts into company_health.json
$artifactsDir = Join-Path $repoRoot "artifacts"
if(-not (Test-Path -LiteralPath $artifactsDir -PathType Container)){
  New-Item -ItemType Directory -Force -Path $artifactsDir | Out-Null
}
$companyHealthPath = Join-Path $artifactsDir "company_health.json"
$policyObj = RC-ReadJsonOrNull $policyPath
$governanceObj = RC-ReadJsonOrNull $governancePath

$policyPresent = $null -ne $policyObj
$governancePresent = $null -ne $governanceObj

$policyOverall = $null
$policyChecksFailed = 0
$policyWarnings = 0
$policySummary = $null
if($policyPresent){
  $policyOverall = $policyObj.overall
  if($policyObj.PSObject.Properties.Name -contains "checks_failed"){
    $policyChecksFailed = [int]$policyObj.checks_failed
  } elseif(($policyObj.PSObject.Properties.Name -contains "summary") -and ($null -ne $policyObj.summary)){
    if($policyObj.summary.PSObject.Properties.Name -contains "failed"){ $policyChecksFailed = [int]$policyObj.summary.failed }
    elseif($policyObj.summary.PSObject.Properties.Name -contains "error"){ $policyChecksFailed = [int]$policyObj.summary.error }
  }
  if(($policyObj.PSObject.Properties.Name -contains "summary") -and ($null -ne $policyObj.summary)){
    if($policyObj.summary.PSObject.Properties.Name -contains "warning"){ $policyWarnings = [int]$policyObj.summary.warning }
    elseif($policyObj.summary.PSObject.Properties.Name -contains "warnings"){ $policyWarnings = [int]$policyObj.summary.warnings }
  }
  if($policyObj.PSObject.Properties.Name -contains "summary"){ $policySummary = $policyObj.summary }
}

$governanceOverall = $null
$governanceErrors = 0
$governanceWarnings = 0
$governanceSummary = $null
if($governancePresent){
  $governanceOverall = $governanceObj.overall
  if($governanceObj.PSObject.Properties.Name -contains "error"){ $governanceErrors = [int]$governanceObj.error }
  elseif(($governanceObj.PSObject.Properties.Name -contains "summary") -and ($governanceObj.summary.PSObject.Properties.Name -contains "error")){ $governanceErrors = [int]$governanceObj.summary.error }
  if($governanceObj.PSObject.Properties.Name -contains "warning"){ $governanceWarnings = [int]$governanceObj.warning }
  elseif(($governanceObj.PSObject.Properties.Name -contains "summary") -and ($governanceObj.summary.PSObject.Properties.Name -contains "warning")){ $governanceWarnings = [int]$governanceObj.summary.warning }
  if($governanceObj.PSObject.Properties.Name -contains "summary"){
    $governanceSummary = $governanceObj.summary
  } else {
    $governanceSummary = @{
      total = $governanceObj.total
      ok = $governanceObj.ok
      warning = $governanceObj.warning
      error = $governanceObj.error
    }
  }
}

$totalErrors = [int]($policyChecksFailed + $governanceErrors)
$totalWarnings = [int]($policyWarnings + $governanceWarnings)
$hasFailSource = $false
if($policyPresent -and $null -ne $policyOverall){
  $p = [string]$policyOverall
  if(($p.ToUpperInvariant() -eq "FAIL") -or ($p.ToUpperInvariant() -eq "ERROR")){ $hasFailSource = $true }
}
if($governancePresent -and $null -ne $governanceOverall){
  $g = [string]$governanceOverall
  if(($g.ToUpperInvariant() -eq "FAIL") -or ($g.ToUpperInvariant() -eq "ERROR")){ $hasFailSource = $true }
}
if($totalErrors -gt 0){ $hasFailSource = $true }

$overall = "PASS"
if($hasFailSource){
  $overall = "FAIL"
} elseif($totalWarnings -gt 0){
  $overall = "WARN"
}

$highlights = @()
if(-not $policyPresent){ $highlights += "policy_check artifact missing" }
if(-not $governancePresent){ $highlights += "governance_check artifact missing" }
if($policyPresent -and ($policyChecksFailed -gt 0)){ $highlights += ("policy_check reports {0} failed checks" -f $policyChecksFailed) }
if($governancePresent -and ($governanceErrors -gt 0)){ $highlights += ("governance_check reports {0} errors" -f $governanceErrors) }
if($governancePresent -and ($governanceWarnings -gt 0)){ $highlights += ("governance_check reports {0} warnings" -f $governanceWarnings) }
if(($highlights.Count -eq 0) -and $policyPresent -and $governancePresent){
  $highlights += "all sources passed without errors"
}

$companyHealth = [ordered]@{
  generated_at = [DateTime]::UtcNow.ToString("o")
  overall = $overall
  sources = [ordered]@{
    policy_check = [ordered]@{
      present = $policyPresent
      path = "artifacts/policy_check.json"
      overall = $policyOverall
      checks_failed = $policyChecksFailed
      summary = $policySummary
    }
    governance_check = [ordered]@{
      present = $governancePresent
      path = "artifacts/governance_check.json"
      overall = $governanceOverall
      error_count = $governanceErrors
      warning_count = $governanceWarnings
      summary = $governanceSummary
    }
  }
  totals = [ordered]@{
    errors = $totalErrors
    warnings = $totalWarnings
  }
  highlights = @($highlights)
}
$companyHealthJson = $companyHealth | ConvertTo-Json -Depth 16
[System.IO.File]::WriteAllText($companyHealthPath, $companyHealthJson, [System.Text.UTF8Encoding]::new($false))
RC-Info ("company health artifact written: {0}" -f $companyHealthPath)

if($governanceRc -ne 0){
  RC-Die ("governance gate failed (rc={0})" -f $governanceRc) $governanceRc
}

RC-Info "OK"
exit 0





