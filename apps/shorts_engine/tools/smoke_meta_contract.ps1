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

function Get-RunIdFromJob([string]$jobPath, [string]$PyExe) {
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

function Assert-MetaContract($m, [string]$ctx) {
  $requiredTop = @(
    "run_id","engine_version","job_hash","job_path","started_at","ended_at",
    "render_duration_ms","layer1_rc","layer1_duration_ms",
    "artifacts","error_type","diagnosis"
  )
  foreach ($k in $requiredTop) {
    Assert-True (($m.PSObject.Properties.Name -contains $k)) "$ctx missing key: $k"
  }
  Assert-True ($m.artifacts -ne $null) "$ctx artifacts is null"
  $requiredArtifacts = @("mp4_path","mp4_bytes","artifacts_ok","cached")
  foreach ($k in $requiredArtifacts) {
    Assert-True (($m.artifacts.PSObject.Properties.Name -contains $k)) "$ctx artifacts missing key: $k"
  }
}

Write-Host "== smoke_meta_contract =="
Set-Location $RepoRoot

# 1) Success render
$out1 = & $Py -m shorts_engine.layer2.cli.render_job --job $Job
$rc1 = $LASTEXITCODE
Assert-True ($rc1 -eq 0) "success render failed rc=$rc1"
$runId1 = Get-RunIdFromOutput -lines $out1
if (-not $runId1) { $runId1 = Get-RunIdFromJob -jobPath (Join-Path $RepoRoot $Job) -PyExe $Py }
Assert-True ($runId1) "success run_id not found"
$meta1Path = Join-Path $RepoRoot ("runs\" + $runId1 + "\meta.json")
Assert-True (Test-Path -LiteralPath $meta1Path) "success meta.json missing: $meta1Path"
$m1 = Get-Content -LiteralPath $meta1Path -Raw | ConvertFrom-Json
Assert-MetaContract -m $m1 -ctx "success"

# 2) Validation fail render (version mismatch)
$tmp = Join-Path $RepoRoot "_junk\smoke_meta_contract"
New-Item -ItemType Directory -Force $tmp | Out-Null
$badJob = Join-Path $tmp "bad_validation_job.json"
$orig = Get-Content -LiteralPath (Join-Path $RepoRoot $Job) -Raw | ConvertFrom-Json
$orig.version = "0.2"
$orig | ConvertTo-Json -Depth 64 | Set-Content -LiteralPath $badJob -Encoding utf8

$out2 = & $Py -m shorts_engine.layer2.cli.render_job --job $badJob
$rc2 = $LASTEXITCODE
Assert-True ($rc2 -eq 2) "validation run expected rc=2, got $rc2"
$runId2 = Get-RunIdFromOutput -lines $out2
if (-not $runId2) { $runId2 = Get-RunIdFromJob -jobPath $badJob -PyExe $Py }
Assert-True ($runId2) "validation run_id not found"
$meta2Path = Join-Path $RepoRoot ("runs\" + $runId2 + "\meta.json")
Assert-True (Test-Path -LiteralPath $meta2Path) "validation meta.json missing: $meta2Path"
$m2 = Get-Content -LiteralPath $meta2Path -Raw | ConvertFrom-Json
Assert-MetaContract -m $m2 -ctx "validation"
Assert-True ($m2.error_type -eq "validation") "validation meta.error_type expected 'validation', got '$($m2.error_type)'"

Remove-Item -Recurse -Force $tmp
Write-Host "OK: smoke_meta_contract passed"
