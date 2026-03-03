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

Write-Host "== smoke_presets =="
Set-Location $RepoRoot

$ls = & $Py -m shorts_engine.layer2.cli.presets list
Assert-True ($LASTEXITCODE -eq 0) "presets list failed"
$lsj = $ls | Select-Object -Last 1 | ConvertFrom-Json
Assert-True ($lsj.ok -eq $true) "presets list returned ok=false"
Assert-True ([int]$lsj.count -ge 1) "expected at least one preset"
Assert-True (($lsj.items | Where-Object { $_.name -eq "tr_psych_v1" }).Count -ge 1) "tr_psych_v1 not found"

$tmp = Join-Path $RepoRoot "_junk\smoke_presets"
New-Item -ItemType Directory -Force $tmp | Out-Null

$baseJobPath = Join-Path $RepoRoot "shorts_engine/layer2/examples/min_job.json"
$base = Get-Content -LiteralPath $baseJobPath -Raw | ConvertFrom-Json

$job1 = Join-Path $tmp "job_p1.json"
$job2 = Join-Path $tmp "job_p2.json"

$base1 = $base | ConvertTo-Json -Depth 50 | ConvertFrom-Json
$base1 | Add-Member -NotePropertyName preset -NotePropertyValue "tr_psych_v1" -Force
$base1.output.path = "output/smoke_presets_p1.mp4"
$base1.subtitles.items = @(
  @{ text = "Kisa satir bir." },
  @{ text = "Kisa satir iki." }
)
$base1 | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $job1 -Encoding utf8

$base2 = $base | ConvertTo-Json -Depth 50 | ConvertFrom-Json
$base2 | Add-Member -NotePropertyName preset -NotePropertyValue "tr_psych_v2_fast" -Force
$base2.output.path = "output/smoke_presets_p2.mp4"
$base2.subtitles.items = @(
  @{ text = "Hizli preset satir." },
  @{ text = "Ikinci satir kisa." }
)
$base2 | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $job2 -Encoding utf8

$r1 = & $Py -m shorts_engine.layer2.cli.render_job --job $job1
Assert-True ($LASTEXITCODE -eq 0) "render_job preset job1 failed"
$run1 = Get-RunId -lines $r1
Assert-True ($run1) "run_id missing for preset job1"

$runDir1 = Get-RunDir -root $RepoRoot -runId $run1
Assert-True ($runDir1) "run dir not found for run1"
$meta1Path = Join-Path $runDir1 "meta.json"
Assert-True (Test-Path -LiteralPath $meta1Path) "meta.json missing for run1"
$meta1 = Get-Content -LiteralPath $meta1Path -Raw | ConvertFrom-Json
Assert-True (($meta1.PSObject.Properties.Name -contains "preset_name")) "meta.preset_name key missing"
Assert-True (($meta1.PSObject.Properties.Name -contains "preset_hash")) "meta.preset_hash key missing"
Assert-True ($meta1.preset_name -eq "tr_psych_v1") "meta.preset_name expected tr_psych_v1"
Assert-True ($meta1.preset_hash) "meta.preset_hash missing"

$r1b = & $Py -m shorts_engine.layer2.cli.render_job --job $job1
Assert-True ($LASTEXITCODE -eq 0) "render_job preset job1 second run failed"
$run1b = Get-RunId -lines $r1b
Assert-True ($run1b -eq $run1) "same job+same preset expected same run_id"

$r2 = & $Py -m shorts_engine.layer2.cli.render_job --job $job2
Assert-True ($LASTEXITCODE -eq 0) "render_job preset job2 failed"
$run2 = Get-RunId -lines $r2
Assert-True ($run2) "run_id missing for preset job2"
Assert-True ($run2 -ne $run1) "different preset expected different run_id"

Remove-Item -Recurse -Force $tmp
Write-Host "OK: smoke_presets passed"
