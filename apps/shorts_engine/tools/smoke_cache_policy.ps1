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

function Get-JobHashRunId([string]$jobPath, [string]$PyExe) {
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

function Get-MetaPath([string]$repo, [string]$runId) {
  return (Join-Path $repo ("runs\" + $runId + "\meta.json"))
}

function Get-StatusPath([string]$repo, [string]$runId) {
  return (Join-Path $repo ("runs\" + $runId + "\status.json"))
}

Write-Host "== smoke_cache_policy =="
Set-Location $RepoRoot

$jobAbs = Join-Path $RepoRoot $Job
Assert-True (Test-Path -LiteralPath $jobAbs) "missing job: $jobAbs"

# 1) First run (force no cache)
$out1 = & $Py -m shorts_engine.layer2.cli.render_job --no-cache --job $Job
$rc1 = $LASTEXITCODE
Assert-True ($rc1 -eq 0) "first run expected rc=0, got $rc1"
$runId1 = Get-RunIdFromOutput -lines $out1
if (-not $runId1) { $runId1 = Get-JobHashRunId -jobPath $jobAbs -PyExe $Py }
Assert-True ($runId1) "first run_id not found"

$meta1Path = Get-MetaPath -repo $RepoRoot -runId $runId1
$status1Path = Get-StatusPath -repo $RepoRoot -runId $runId1
Assert-True (Test-Path -LiteralPath $meta1Path) "missing meta after first run: $meta1Path"
Assert-True (Test-Path -LiteralPath $status1Path) "missing status after first run: $status1Path"
$m1 = Get-Content -LiteralPath $meta1Path -Raw | ConvertFrom-Json
$s1 = Get-Content -LiteralPath $status1Path -Raw | ConvertFrom-Json
Assert-True ($m1.cached -eq $false) "first run meta.cached expected false"
Assert-True ($m1.cache_hit -eq $false) "first run meta.cache_hit expected false"
if (-not [string]::IsNullOrWhiteSpace([string]$m1.cache_reason)) {
  Assert-True ([string]$m1.cache_reason -ne "meta+mp4 ok") "first run cache_reason should not indicate cache hit"
}

$mp4Path = $null
try { $mp4Path = [string]$m1.artifacts.mp4_path } catch { $mp4Path = $null }
if ([string]::IsNullOrWhiteSpace($mp4Path)) {
  try { $mp4Path = [string]$m1.out_path } catch {}
}
Assert-True (-not [string]::IsNullOrWhiteSpace($mp4Path)) "first run mp4 path missing"
if (-not ([System.IO.Path]::IsPathRooted($mp4Path))) {
  $mp4Path = Join-Path $RepoRoot $mp4Path
}
Assert-True (Test-Path -LiteralPath $mp4Path) "first run mp4 missing on disk: $mp4Path"
$bytes1 = (Get-Item -LiteralPath $mp4Path).Length
Assert-True ($bytes1 -gt 0) "first run mp4 bytes invalid"

# 2) Second run (default cache policy should reuse)
$out2 = & $Py -m shorts_engine.layer2.cli.render_job --job $Job
$rc2 = $LASTEXITCODE
Assert-True ($rc2 -eq 0) "second run expected rc=0, got $rc2"
$runId2 = Get-RunIdFromOutput -lines $out2
if (-not $runId2) { $runId2 = Get-JobHashRunId -jobPath $jobAbs -PyExe $Py }
Assert-True ($runId2) "second run_id not found"
Assert-True ($runId2 -eq $runId1) "expected deterministic run_id, got $runId1 vs $runId2"

$meta2Path = Get-MetaPath -repo $RepoRoot -runId $runId2
$status2Path = Get-StatusPath -repo $RepoRoot -runId $runId2
$m2 = Get-Content -LiteralPath $meta2Path -Raw | ConvertFrom-Json
$s2 = Get-Content -LiteralPath $status2Path -Raw | ConvertFrom-Json
Assert-True ($m2.cached -eq $true) "second run meta.cached expected true"
if ($s2.PSObject.Properties.Name -contains "cached") {
  Assert-True ($s2.cached -eq $true) "second run status.cached expected true when present"
}
Assert-True ($m2.cache_hit -eq $true) "second run meta.cache_hit expected true"
Assert-True (-not [string]::IsNullOrWhiteSpace([string]$m2.cache_reason)) "second run cache_reason missing"

$mp4Path2 = [string]$m2.artifacts.mp4_path
if ([string]::IsNullOrWhiteSpace($mp4Path2)) { $mp4Path2 = $mp4Path }
if (-not ([System.IO.Path]::IsPathRooted($mp4Path2))) {
  $mp4Path2 = Join-Path $RepoRoot $mp4Path2
}
Assert-True (Test-Path -LiteralPath $mp4Path2) "second run mp4 missing on disk: $mp4Path2"
$bytes2 = (Get-Item -LiteralPath $mp4Path2).Length
Assert-True ($bytes2 -eq $bytes1) "mp4 byte stability failed: first=$bytes1 second=$bytes2"

# 3) Batch report counters
$tmp = Join-Path $RepoRoot "_junk\smoke_cache_policy"
New-Item -ItemType Directory -Force $tmp | Out-Null
$jobsFile = Join-Path $tmp "jobs.txt"
$reportPath = Join-Path $tmp "batch_report.json"
Set-Content -LiteralPath $jobsFile -Value $Job -Encoding utf8

$bout = & $Py -m shorts_engine.layer2.cli.render_batch --jobs-file $jobsFile --json-out $reportPath
$brc = $LASTEXITCODE
Assert-True (($brc -eq 0) -or ($brc -eq 2)) "batch run failed with unexpected rc=$brc"
Assert-True (Test-Path -LiteralPath $reportPath) "batch report missing: $reportPath"
$br = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
Assert-True ($br.summary -ne $null) "batch report summary missing"
$cachedCount = [int]($br.summary.cached_count)
$renderedCount = [int]($br.summary.rendered_count)
$total = [int]($br.summary.total)
Assert-True ($cachedCount -ge 1) "expected cached_count>=1, got $cachedCount"
Assert-True (($cachedCount + $renderedCount) -eq $total) "cached_count + rendered_count mismatch total"

Remove-Item -Recurse -Force $tmp
Write-Host "OK: smoke_cache_policy passed"
