param(
  [string]$RepoRoot = (git rev-parse --show-toplevel),
  [string]$Py = "python",
  [string]$Job = "shorts_engine/layer2/examples/min_job.json"
)

$ErrorActionPreference = "Stop"

function Assert-True($cond, $msg) { if (-not $cond) { throw "ASSERT FAIL: $msg" } }

function Get-RunIdFromOutput([string[]]$lines) {
  $m = $lines | Select-String -Pattern "run_id=([0-9a-fA-F_]+)" | Select-Object -First 1
  if ($m -and $m.Matches.Count -gt 0) { return $m.Matches[0].Groups[1].Value }
  return $null
}

function Get-DeterministicRunId([string]$jobPath, [string]$PyExe) {
  $code = @"
import json, hashlib, sys
p = sys.argv[1]
raw = json.load(open(p, "r", encoding="utf-8"))
s = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
print(hashlib.sha256(s.encode("utf-8")).hexdigest()[:12])
"@
  $rid = & $PyExe -c $code $jobPath
  if ($LASTEXITCODE -ne 0) { return $null }
  return ($rid | Select-Object -First 1).Trim()
}

Write-Host "== smoke_cleanup =="
Set-Location $RepoRoot

$jobAbs = Join-Path $RepoRoot $Job
Assert-True (Test-Path -LiteralPath $jobAbs) "missing job: $jobAbs"

# 1) Create runs: no-cache success, cached success, and validation failure.
$o1 = & $Py -m shorts_engine.layer2.cli.render_job --no-cache --job $Job
Assert-True ($LASTEXITCODE -eq 0) "render #1 failed"
$run1 = Get-RunIdFromOutput -lines $o1
if (-not $run1) { $run1 = Get-DeterministicRunId -jobPath $jobAbs -PyExe $Py }
Assert-True ($run1) "run1 id missing"

$o2 = & $Py -m shorts_engine.layer2.cli.render_job --job $Job
Assert-True ($LASTEXITCODE -eq 0) "render #2 failed"

$tmp = Join-Path $RepoRoot "_junk\smoke_cleanup"
New-Item -ItemType Directory -Force $tmp | Out-Null
$badJob = Join-Path $tmp "bad_validation_job.json"
$j = Get-Content -LiteralPath $jobAbs -Raw | ConvertFrom-Json
$j.version = "0.2"
$j | ConvertTo-Json -Depth 64 | Set-Content -LiteralPath $badJob -Encoding utf8

$oBad = & $Py -m shorts_engine.layer2.cli.render_job --job $badJob
Assert-True ($LASTEXITCODE -eq 2) "validation render expected rc=2"
$badRun = Get-RunIdFromOutput -lines $oBad
if (-not $badRun) { $badRun = Get-DeterministicRunId -jobPath $badJob -PyExe $Py }
Assert-True ($badRun) "failed run id missing"

# 2) DRY-RUN over real runs
$dryReport = Join-Path $tmp "cleanup_dry.json"
& $Py -m shorts_engine.layer2.cli.clean_runs `
  --repo-root $RepoRoot `
  --keep-last 1 `
  --keep-days 0 `
  --keep-failed `
  --keep-batch-last 0 `
  --dry-run `
  --json-out $dryReport | Out-Host
Assert-True ($LASTEXITCODE -eq 0) "clean_runs dry-run failed"
Assert-True (Test-Path -LiteralPath $dryReport) "dry report missing"
$dry = Get-Content -LiteralPath $dryReport -Raw | ConvertFrom-Json
Assert-True ([int]$dry.counts.delete_runs -ge 1) "expected delete_runs >= 1 in dry-run"
Assert-True (($dry.kept_reasons.PSObject.Properties.Name -contains $badRun)) "failed run should be kept (keep_failed)"

# 3) APPLY over temp sandbox runs dir (no real deletion)
$sandbox = Join-Path $tmp "sandbox_runs"
$sandboxRuns = Join-Path $sandbox "runs"
New-Item -ItemType Directory -Force $sandboxRuns | Out-Null

$allRunDirs = Get-ChildItem -LiteralPath (Join-Path $RepoRoot "runs") -Directory |
  Where-Object { $_.Name -match "^[0-9a-fA-F]{8,16}$" -and (Test-Path -LiteralPath (Join-Path $_.FullName "meta.json")) } |
  Sort-Object LastWriteTime -Descending

$successRuns = @()
foreach ($r in $allRunDirs) {
  try {
    $m = Get-Content -LiteralPath (Join-Path $r.FullName "meta.json") -Raw | ConvertFrom-Json
    $isFailed = $false
    if ($null -ne $m.error_type -and [string]$m.error_type -ne "") { $isFailed = $true }
    if ($m.artifacts -and $m.artifacts.artifacts_ok -eq $false) { $isFailed = $true }
    if (-not $isFailed) { $successRuns += $r }
  } catch {}
}

if ($successRuns.Count -lt 2) {
  # Create another valid deterministic run with a tiny output-path variation.
  $altJob = Join-Path $tmp "alt_success_job.json"
  $jok = Get-Content -LiteralPath $jobAbs -Raw | ConvertFrom-Json
  if (-not $jok.output) { $jok | Add-Member -NotePropertyName output -NotePropertyValue (@{}) -Force }
  $jok.output.path = "output/smoke_cleanup_alt.mp4"
  $jok | ConvertTo-Json -Depth 64 | Set-Content -LiteralPath $altJob -Encoding utf8
  & $Py -m shorts_engine.layer2.cli.render_job --no-cache --job $altJob | Out-Null
  Assert-True ($LASTEXITCODE -eq 0) "failed to create second success run for cleanup smoke"
  $allRunDirs = Get-ChildItem -LiteralPath (Join-Path $RepoRoot "runs") -Directory |
    Where-Object { $_.Name -match "^[0-9a-fA-F]{8,16}$" -and (Test-Path -LiteralPath (Join-Path $_.FullName "meta.json")) } |
    Sort-Object LastWriteTime -Descending
  $successRuns = @()
  foreach ($r in $allRunDirs) {
    try {
      $m = Get-Content -LiteralPath (Join-Path $r.FullName "meta.json") -Raw | ConvertFrom-Json
      $isFailed = $false
      if ($null -ne $m.error_type -and [string]$m.error_type -ne "") { $isFailed = $true }
      if ($m.artifacts -and $m.artifacts.artifacts_ok -eq $false) { $isFailed = $true }
      if (-not $isFailed) { $successRuns += $r }
    } catch {}
  }
}
Assert-True ($successRuns.Count -ge 2) "need at least two successful runs for sandbox"

$copyRunIds = @($successRuns[0].Name, $successRuns[1].Name)
if ($copyRunIds -notcontains $badRun) { $copyRunIds += $badRun }

foreach ($rid in $copyRunIds) {
  $src = Join-Path $RepoRoot ("runs\" + $rid)
  if (Test-Path -LiteralPath $src) {
    Copy-Item -LiteralPath $src -Destination $sandboxRuns -Recurse -Force
  }
}

# copy one batch dir if exists
$srcBatchRoot = Join-Path $RepoRoot "runs\_batch"
$dstBatchRoot = Join-Path $sandboxRuns "_batch"
if (Test-Path -LiteralPath $srcBatchRoot) {
  New-Item -ItemType Directory -Force $dstBatchRoot | Out-Null
  $b = Get-ChildItem -LiteralPath $srcBatchRoot -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($b) { Copy-Item -LiteralPath $b.FullName -Destination $dstBatchRoot -Recurse -Force }
}

$applyReport = Join-Path $tmp "cleanup_apply.json"
& $Py -m shorts_engine.layer2.cli.clean_runs `
  --runs-dir $sandboxRuns `
  --keep-last 1 `
  --keep-days 0 `
  --keep-failed `
  --keep-batch-last 0 `
  --apply `
  --json-out $applyReport | Out-Host
Assert-True ($LASTEXITCODE -eq 0) "clean_runs apply failed"
Assert-True (Test-Path -LiteralPath $applyReport) "apply report missing"
$ap = Get-Content -LiteralPath $applyReport -Raw | ConvertFrom-Json
Assert-True ([int]$ap.counts.delete_runs -ge 1) "expected apply delete_runs >= 1"

$failedStillThere = Test-Path -LiteralPath (Join-Path $sandboxRuns $badRun)
Assert-True ($failedStillThere) "failed run should remain in sandbox (keep_failed)"

Remove-Item -Recurse -Force $tmp
Write-Host "OK: smoke_cleanup passed"
