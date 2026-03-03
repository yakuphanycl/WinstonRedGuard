param(
  [string]$RepoRoot = (git rev-parse --show-toplevel),
  [string]$Py = "python"
)

$ErrorActionPreference = "Stop"

function Assert-True($cond, $msg) {
  if (-not $cond) { throw "ASSERT FAIL: $msg" }
}

function Get-RunId([string[]]$lines) {
  $m = $lines | Select-String -Pattern "run_id=([0-9a-fA-F_]+)" | Select-Object -First 1
  if ($m -and $m.Matches.Count -gt 0) { return $m.Matches[0].Groups[1].Value }
  return $null
}

function Get-RunDir([string]$root, [string]$runId) {
  $cands = @(
    (Join-Path $root ("runs\" + $runId)),
    (Join-Path $root ("shorts_engine\runs\" + $runId))
  )
  foreach ($c in $cands) {
    if (Test-Path -LiteralPath $c) { return $c }
  }
  return $null
}

Write-Host "== smoke_thumb =="
Set-Location $RepoRoot

$job = "shorts_engine/layer2/examples/min_job.json"
$renderOut = & $Py -m shorts_engine.layer2.cli.render_job --job $job --no-cache
Assert-True ($LASTEXITCODE -eq 0) "render_job failed for thumb smoke"

$runId = Get-RunId -lines $renderOut
Assert-True ($runId) "missing run_id from render output"

$runDir = Get-RunDir -root $RepoRoot -runId $runId
Assert-True ($runDir) "run dir not found for run_id=$runId"
$metaPath = Join-Path $runDir "meta.json"
Assert-True (Test-Path -LiteralPath $metaPath) "meta.json not found: $metaPath"

$thumbOut = & $Py -m shorts_engine.layer2.cli.make_thumb --run-id $runId --repo-root $RepoRoot --mode frame
Assert-True ($LASTEXITCODE -eq 0) "make_thumb frame failed"
$thumbJson = $thumbOut | Select-Object -Last 1 | ConvertFrom-Json
Assert-True ($thumbJson.ok -eq $true) "make_thumb frame returned ok=false"
Assert-True ($thumbJson.out_path) "make_thumb frame missing out_path"
Assert-True (Test-Path -LiteralPath $thumbJson.out_path) "thumb file not found: $($thumbJson.out_path)"

$meta = Get-Content -LiteralPath $metaPath -Raw | ConvertFrom-Json
Assert-True ($meta.artifacts -ne $null) "meta.artifacts missing"
Assert-True (($meta.artifacts.PSObject.Properties.Name -contains "thumb_path")) "meta.artifacts.thumb_path missing"
Assert-True (($meta.artifacts.PSObject.Properties.Name -contains "thumb_bytes")) "meta.artifacts.thumb_bytes missing"
Assert-True (($meta.artifacts.PSObject.Properties.Name -contains "thumb_ok")) "meta.artifacts.thumb_ok missing"
Assert-True ([bool]$meta.artifacts.thumb_ok) "meta.artifacts.thumb_ok expected true"
Assert-True ([int]$meta.artifacts.thumb_bytes -gt 0) "meta.artifacts.thumb_bytes expected > 0"

# default policy: if thumb already exists and --force is not set, second run should skip/cached
$thumbOut2 = & $Py -m shorts_engine.layer2.cli.make_thumb --run-id $runId --repo-root $RepoRoot --mode frame
Assert-True ($LASTEXITCODE -eq 0) "make_thumb second call failed"
$thumbJson2 = $thumbOut2 | Select-Object -Last 1 | ConvertFrom-Json
Assert-True ($thumbJson2.ok -eq $true) "make_thumb second call returned ok=false"
Assert-True ($thumbJson2.cached -eq $true) "make_thumb second call expected cached=true"

Write-Host ("OK: smoke_thumb passed (run_id={0})" -f $runId)
