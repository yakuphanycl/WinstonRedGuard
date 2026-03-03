param(
  [string]$Job = "layer2/examples/min_job.json",
  [switch]$Json,
  [switch]$CompatLegacy
)

$ErrorActionPreference = "Stop"

function Emit-Json($obj) {
  # Stable JSON output for CI parsing
  $obj | ConvertTo-Json -Depth 8 -Compress
}

function Try-Read-MetaMetrics($metaPath) {
  if (-not $metaPath) { return $null }
  if (-not (Test-Path -LiteralPath $metaPath)) { return $null }
  try {
    $txt = Get-Content -LiteralPath $metaPath -Raw
    $obj = $txt | ConvertFrom-Json
    $dur = $null
    $ts0 = $null
    $ts1 = $null
    if ($obj.PSObject.Properties.Name -contains "render_duration_ms") { $dur = $obj.render_duration_ms }
    if ($obj.PSObject.Properties.Name -contains "render_start_ts")    { $ts0 = $obj.render_start_ts }
    if ($obj.PSObject.Properties.Name -contains "render_end_ts")      { $ts1 = $obj.render_end_ts }
    return @{
      render_duration_ms = $dur
      render_start_ts = $ts0
      render_end_ts = $ts1
    }
  } catch {
    return $null
  }
}

function Get-RequiredArtifacts {
  param([string]$Py = "python")

  try {
    $reqJson = & $Py -c "import json; from layer2.core.run_store import REQUIRED_ARTIFACTS; print(json.dumps(REQUIRED_ARTIFACTS))" 2>$null
    if (-not $reqJson) { throw "empty REQUIRED_ARTIFACTS json" }
    $parsed = $reqJson | ConvertFrom-Json
    $arr = @()
    foreach ($x in @($parsed)) { $arr += [string]$x }
    if ($arr.Count -eq 0) { throw "no required artifacts parsed" }
    return [pscustomobject]@{
      required = $arr
      source = "python"
    }
  } catch {
    Write-Host "WARN: could not import REQUIRED_ARTIFACTS via python; falling back to minimal list." -ForegroundColor Yellow
    return [pscustomobject]@{
      required = @("job.layer2.json", "job.layer1.json", "meta.json")
      source = "fallback"
    }
  }
}

function Get-RunStoreVersionExpected {
  param([string]$Py = "python")

  try {
    $v = & $Py -c "from layer2.core.run_store import RUN_STORE_VERSION; print(RUN_STORE_VERSION)" 2>$null
    if (-not $v) { throw "empty RUN_STORE_VERSION" }
    return [string]$v
  } catch {
    Write-Host "WARN: could not import RUN_STORE_VERSION via python; using UNKNOWN." -ForegroundColor Yellow
    return "UNKNOWN"
  }
}

function Try-Get-RunStoreVersionFromMetaPath {
  param([string]$MetaPath)
  if (-not $MetaPath) { return "UNKNOWN" }
  if (-not (Test-Path -LiteralPath $MetaPath)) { return "UNKNOWN" }
  try {
    $metaObj = Get-Content -LiteralPath $MetaPath -Raw | ConvertFrom-Json
    if ($metaObj.PSObject.Properties.Name -contains "run_store_version" -and $metaObj.run_store_version) {
      return [string]$metaObj.run_store_version
    }
  } catch {
  }
  return "UNKNOWN"
}

function Test-VersionLessThan {
  param(
    [string]$Actual,
    [string]$Expected
  )
  if ([string]::IsNullOrWhiteSpace($Actual) -or [string]::IsNullOrWhiteSpace($Expected)) { return $false }
  try {
    $a = [version]$Actual
    $e = [version]$Expected
    return ($a -lt $e)
  } catch {
    Write-Host "WARN: could not parse run_store_version as [version] ('$Actual' vs '$Expected'); using lexical compare." -ForegroundColor Yellow
    return ([string]::CompareOrdinal($Actual, $Expected) -lt 0)
  }
}

function Get-CompatMode {
  param(
    [switch]$CompatLegacy,
    [string]$RunStoreVersionActual,
    [string]$RunStoreVersionExpected
  )
  if ($CompatLegacy) { return "legacy" }
  if ($RunStoreVersionActual -eq "UNKNOWN") { return "legacy" }
  if ($RunStoreVersionExpected -ne "UNKNOWN" -and (Test-VersionLessThan -Actual $RunStoreVersionActual -Expected $RunStoreVersionExpected)) {
    return "legacy"
  }
  return "canonical"
}

function Test-RequiredArtifacts {
  param(
    [string]$RunDir,
    [string]$CompatMode
  )

  $contract = Get-RequiredArtifacts
  $required = @($contract.required)
  $missing = @()
  $substitutions = @()
  $legacyProbesUsed = $false

  # Canonical -> legacy substitution map (compat mode only).
  $legacyMap = @{
    "meta.json" = "render_meta.json"
    "stdout.log" = "render_trace.txt"
    "job.layer2.json" = "layer2_job.json"
  }

  $resolvedMetaPath = $null
  $resolvedTracePath = $null
  $resolvedJobLayer2Path = $null

  foreach ($rel in $required) {
    if ($rel -like "*.mp4" -or $rel -match '[\*\?\[]') {
      $mp4Files = Get-ChildItem -LiteralPath $RunDir -Filter "*.mp4" -File -ErrorAction SilentlyContinue
      if (-not $mp4Files -or $mp4Files.Count -eq 0) {
        $missing += "*.mp4(min_bytes=1024)"
      } else {
        $okMp4 = $false
        foreach ($f in $mp4Files) {
          if ($f.Length -ge 1024) {
            $okMp4 = $true
            break
          }
        }
        if (-not $okMp4) { $missing += "*.mp4(min_bytes=1024)" }
      }
      continue
    }

    $p = Join-Path $RunDir $rel
    if (Test-Path -LiteralPath $p) {
      if ($rel -eq "meta.json") { $resolvedMetaPath = $p }
      if ($rel -eq "stdout.log") { $resolvedTracePath = $p }
      if ($rel -eq "job.layer2.json") { $resolvedJobLayer2Path = $p }
      continue
    }

    if ($CompatMode -eq "legacy" -and $legacyMap.ContainsKey($rel)) {
      $legacyRel = [string]$legacyMap[$rel]
      $legacyPath = Join-Path $RunDir $legacyRel
      if (Test-Path -LiteralPath $legacyPath) {
        $legacyProbesUsed = $true
        $substitutions += [pscustomobject]@{
          required = $rel
          used = $legacyRel
        }
        if ($rel -eq "meta.json") { $resolvedMetaPath = $legacyPath }
        if ($rel -eq "stdout.log") { $resolvedTracePath = $legacyPath }
        if ($rel -eq "job.layer2.json") { $resolvedJobLayer2Path = $legacyPath }
        continue
      }
    }

    $missing += $rel
  }

  return [pscustomobject]@{
    artifacts_ok_fs = ($missing.Count -eq 0)
    artifacts_missing = @($missing)
    artifacts_contract_source = $contract.source
    artifacts_substitutions = @($substitutions)
    legacy_probes_used = [bool]$legacyProbesUsed
    resolved_meta_path = $resolvedMetaPath
    resolved_trace_path = $resolvedTracePath
    resolved_job_layer2_path = $resolvedJobLayer2Path
  }
}

function Try-Resolve-RunArtifacts($runId, $outPath) {
  if (-not $runId) { return $null }
  $runsRoot = Join-Path (Get-Location).Path "runs"
  $runDir = Join-Path $runsRoot $runId
  if (-not (Test-Path -LiteralPath $runDir)) { return $null }

  # Prefer run_dir/run_path from canonical meta.json if present.
  $metaJsonPath = Join-Path $runDir "meta.json"
  if (Test-Path -LiteralPath $metaJsonPath) {
    try {
      $metaObj = Get-Content -LiteralPath $metaJsonPath -Raw | ConvertFrom-Json
      if ($metaObj.PSObject.Properties.Name -contains "run_dir" -and $metaObj.run_dir) {
        $cand = [string]$metaObj.run_dir
        if (Test-Path -LiteralPath $cand) { $runDir = $cand }
      } elseif ($metaObj.PSObject.Properties.Name -contains "run_path" -and $metaObj.run_path) {
        $cand = [string]$metaObj.run_path
        if (Test-Path -LiteralPath $cand) { $runDir = $cand }
      }
    } catch {
      # best effort
    }
  }

  $runStoreExpected = Get-RunStoreVersionExpected
  $runStoreActual = Try-Get-RunStoreVersionFromMetaPath -MetaPath $metaJsonPath
  $compatMode = Get-CompatMode -CompatLegacy:$CompatLegacy -RunStoreVersionActual $runStoreActual -RunStoreVersionExpected $runStoreExpected

  $fs = Test-RequiredArtifacts -RunDir $runDir -CompatMode $compatMode
  # Re-read actual version from resolved meta path (canonical or substituted).
  $resolvedActualVersion = Try-Get-RunStoreVersionFromMetaPath -MetaPath $fs.resolved_meta_path
  if ($resolvedActualVersion -ne "UNKNOWN") { $runStoreActual = $resolvedActualVersion }

  $l1job = Join-Path $runDir "job.layer1.json"
  $present = @{
    run_dir = $runDir
    meta_path = $fs.resolved_meta_path
    trace_path = $fs.resolved_trace_path
    layer2_job_path = $fs.resolved_job_layer2_path
    layer1_job_path = $(if (Test-Path -LiteralPath $l1job) { $l1job } else { $null })
    artifact_mp4_path = $outPath
    run_store_version = $runStoreActual
    run_store_version_expected = $runStoreExpected
    compat_mode = $compatMode
    legacy_probes_used = [bool]$fs.legacy_probes_used
    resolved_meta_path = $fs.resolved_meta_path
    resolved_trace_path = $fs.resolved_trace_path
    resolved_job_layer2_path = $fs.resolved_job_layer2_path
    artifacts_substitutions = @($fs.artifacts_substitutions)
  }

  $present.artifacts_missing = @($fs.artifacts_missing)
  $present.artifacts_ok_fs = [bool]$fs.artifacts_ok_fs
  $present.artifacts_contract_source = [string]$fs.artifacts_contract_source
  # Keep backwards-compatible field name, but compute from filesystem contract.
  $present.artifacts_ok = $present.artifacts_ok_fs
  $present.run_store_version_match = $(if ($runStoreActual -eq "UNKNOWN" -or $runStoreExpected -eq "UNKNOWN") { $null } else { ($runStoreActual -eq $runStoreExpected) })

  return $present
}

function Parse-ResultLine($text) {
  # Parse: RESULT ok rc=0 out=output\test.mp4 run_id=... cached=True|False
  $s = ($text | Out-String)
  $m = [regex]::Match($s, 'RESULT\s+ok\s+rc=(\d+)\s+out=([^\s]+)\s+run_id=([0-9a-fA-F]+)\s+cached=(True|False)', 'IgnoreCase')
  if (-not $m.Success) {
    return $null
  }
  return @{
    rc = [int]$m.Groups[1].Value
    out = $m.Groups[2].Value
    run_id = $m.Groups[3].Value
    cached = ($m.Groups[4].Value.ToLower() -eq "true")
  }
}

function Die($msg) {
  if ($Json) {
    Emit-Json @{
      ok = $false
      rc = 1
      error = $msg
      root = (Get-Location).Path
      job = $Job
    }
  } else {
    Write-Error $msg
  }
  exit 1
}

if (-not $Json) {
  Write-Host "== shorts_engine verification ==" -ForegroundColor Cyan
}

# 1) Resolve root
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# Normalize job path:
# If caller passes "shorts_engine/..." while we already cd into root,
# strip that prefix to avoid surprising "job not found".
if ($Job -match '^[\\/]*shorts_engine[\\/]+(.+)$') {
  $Job = $Matches[1]
}

if (-not $Json) {
  Write-Host "Root:" $root
}

# 2) Sanity checks
$files = @(
  "layer2/cli/render_job.py",
  "layer2/core/render.py",
  "layer2/core/validate_job.py"
)

foreach ($f in $files) {
  if (!(Test-Path $f)) {
    Die "missing required file: $f"
  }
}

if (!(Test-Path $Job)) {
  Die "job not found: $Job"
}

# 3) Compile checks
if (-not $Json) {
  Write-Host "→ python -m py_compile" -ForegroundColor Yellow
}

$compileOut = & python -m py_compile `
  layer2/cli/render_job.py `
  layer2/core/render.py `
  layer2/core/validate_job.py 2>&1
$compileRc = $LASTEXITCODE

if ($compileRc -ne 0) {
  if ($Json) {
    Emit-Json @{
      ok = $false
      rc = $compileRc
      step = "py_compile"
      root = $root
      job = $Job
      output = ($compileOut | Out-String).Trim()
    }
    exit $compileRc
  }
  Die "py_compile failed"
}

# 4) Smoke render
if (-not $Json) {
  Write-Host "→ render smoke test ($Job)" -ForegroundColor Yellow
}

$renderOut = & python -m layer2.cli.render_job --job $Job 2>&1
$renderRc = $LASTEXITCODE

if ($renderRc -ne 0) {
  if ($Json) {
    Emit-Json @{
      ok = $false
      rc = $renderRc
      step = "render_job"
      root = $root
      job = $Job
      output = ($renderOut | Out-String).Trim()
    }
    exit $renderRc
  }
  Die "render_job failed"
}

if (-not $Json) {
  Write-Host $renderOut
}

# Try parse RESULT line (best-effort)
$parsed = Parse-ResultLine $renderOut

# 5) Output check
$mp4 = "output/test.mp4"
if ($parsed -and $parsed.out) {
  # If CLI reported out path, prefer it
  $mp4 = $parsed.out
}

# Best-effort resolve run artifacts (if runs/<run_id>/ exists)
$art = Try-Resolve-RunArtifacts $(if ($parsed) { $parsed.run_id } else { $null }) $mp4

if (!(Test-Path $mp4)) {
  Die "output not found: $mp4"
}

$item = Get-Item $mp4
$size = $item.Length
if ($size -le 0) {
  Die "output file is empty"
}

if ($Json) {
  $mm = $(if ($art -and $art.meta_path) { Try-Read-MetaMetrics $art.meta_path } else { $null })
  $runStoreExpected = $(if ($art -and $art.run_store_version_expected) { $art.run_store_version_expected } else { Get-RunStoreVersionExpected })
  $runStoreActual = $(if ($art -and $art.run_store_version) { $art.run_store_version } else { "UNKNOWN" })
  $runStoreMatch = $(if ($art -and $art.run_store_version_match -ne $null) { $art.run_store_version_match } else { $(if ($runStoreActual -eq "UNKNOWN" -or $runStoreExpected -eq "UNKNOWN") { $null } else { ($runStoreActual -eq $runStoreExpected) }) })

  Emit-Json @{
    ok = $true
    rc = 0
    root = $root
    job = $Job
    output_path = $mp4
    output_bytes = $size
    output_mtime = $item.LastWriteTime.ToString("o")
    compile_rc = $compileRc
    render_rc = $renderRc
    # Best-effort: if RESULT line exists
    run_id = $(if ($parsed) { $parsed.run_id } else { $null })
    cached = $(if ($parsed -and $parsed.ContainsKey("cached")) { $parsed.cached } else { $null })
    # Best-effort: run artifacts (only if runs/<run_id>/ exists)
    run_dir = $(if ($art) { $art.run_dir } else { $null })
    meta_path = $(if ($art) { $art.meta_path } else { $null })
    trace_path = $(if ($art) { $art.trace_path } else { $null })
    artifacts_ok = $(if ($art) { $art.artifacts_ok } else { $null })
    artifacts_ok_fs = $(if ($art) { $art.artifacts_ok_fs } else { $null })
    artifacts_missing = $(if ($art) { @($art.artifacts_missing) } else { @() })
    artifacts_contract_source = $(if ($art) { $art.artifacts_contract_source } else { $null })
    artifacts_substitutions = $(if ($art) { @($art.artifacts_substitutions) } else { @() })
    compat_mode = $(if ($art) { $art.compat_mode } else { "canonical" })
    legacy_probes_used = $(if ($art) { $art.legacy_probes_used } else { $false })
    resolved_meta_path = $(if ($art) { $art.resolved_meta_path } else { $null })
    resolved_trace_path = $(if ($art) { $art.resolved_trace_path } else { $null })
    resolved_job_layer2_path = $(if ($art) { $art.resolved_job_layer2_path } else { $null })
    run_store_version = $runStoreActual
    run_store_version_expected = $runStoreExpected
    run_store_version_match = $runStoreMatch
    # Observability (best-effort, from render_meta.json if present)
    render_duration_ms = $(if ($mm) { $mm.render_duration_ms } else { $null })
    render_start_ts = $(if ($mm) { $mm.render_start_ts } else { $null })
    render_end_ts = $(if ($mm) { $mm.render_end_ts } else { $null })
  }
  exit 0
} else {
  Write-Host ""
  Write-Host "✔ VERIFICATION OK" -ForegroundColor Green
  Write-Host "output: $mp4 ($size bytes)"
}
