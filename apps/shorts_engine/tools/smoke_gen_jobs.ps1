param(
  [string]$RepoRoot = (git rev-parse --show-toplevel),
  [string]$Py = "python"
)

$ErrorActionPreference = "Stop"

function Assert-True($cond, $msg) { if (-not $cond) { throw "ASSERT FAIL: $msg" } }
function Utf8NoBomWrite([string]$path, [string]$txt) {
  [System.IO.File]::WriteAllText($path, $txt, [System.Text.UTF8Encoding]::new($false))
}

Write-Host "== smoke_gen_jobs =="
Set-Location $RepoRoot

$tmp = Join-Path $RepoRoot "_junk\smoke_gen_jobs"
$inDir = Join-Path $tmp "in"
$outA = Join-Path $tmp "out_a"
$outB = Join-Path $tmp "out_b"
New-Item -ItemType Directory -Force $inDir | Out-Null
New-Item -ItemType Directory -Force $outA | Out-Null
New-Item -ItemType Directory -Force $outB | Out-Null

$csv = Join-Path $inDir "rows.csv"
$tpl = Join-Path $inDir "template.json"

$csvTxt = @"
id,hook,body,ending,duration_sec,tags
a1,Hook A,Body A,End A,8,"alpha,beta"
a2,Hook B,Body B,End B,9,beta
a3,Hook C,Body C,End C,10,gamma
"@
Utf8NoBomWrite $csv $csvTxt

$templateObj = @{
  version = "0.5"
  output = @{ path = "output/{{id}}.mp4" }
  video = @{ resolution = "1080x1920"; fps = 30; duration_sec = 8 }
  hook = "{{hook}}"
  pattern_break = "{{body}}"
  loop_ending = "{{ending}}"
  subtitles = @{
    items = @(
      @{ text = "{{hook}}" },
      @{ text = "{{body}}" },
      @{ text = "{{ending}}" }
    )
  }
}
$tplTxt = $templateObj | ConvertTo-Json -Depth 32
Utf8NoBomWrite $tpl $tplTxt

$manifestA = Join-Path $outA "manifest.json"
$jobsA = Join-Path $outA "jobs.txt"

# 1) First generation
& $Py -m shorts_engine.layer2.cli.gen_jobs --input $csv --template $tpl --out-dir $outA --manifest-out $manifestA --jobs-file-out $jobsA | Out-Host
Assert-True ($LASTEXITCODE -eq 0) "gen_jobs first run failed"
Assert-True (Test-Path -LiteralPath $manifestA) "manifest missing after first run"
Assert-True (Test-Path -LiteralPath $jobsA) "jobs.txt missing after first run"
$m1 = Get-Content -LiteralPath $manifestA -Raw | ConvertFrom-Json
Assert-True ($m1.schema_version -eq "0.1") "manifest schema_version expected 0.1"
Assert-True ($m1.items.Count -eq 3) "manifest items expected 3"
Assert-True (-not [string]::IsNullOrWhiteSpace([string]$m1.hashes.manifest_sha1)) "manifest_sha1 missing"
$linesA = Get-Content -LiteralPath $jobsA | Where-Object { $_ -and $_.Trim() -ne "" }
Assert-True ($linesA.Count -eq 3) "jobs.txt expected 3 lines"
foreach ($jp in $linesA) {
  Assert-True (Test-Path -LiteralPath $jp) "generated job file missing: $jp"
  $j = Get-Content -LiteralPath $jp -Raw | ConvertFrom-Json
  Assert-True ($j.version -eq "0.5") "generated job version expected 0.5"
}

# 2) Determinism/skip behavior in same out-dir
& $Py -m shorts_engine.layer2.cli.gen_jobs --input $csv --template $tpl --out-dir $outA --manifest-out $manifestA --jobs-file-out $jobsA | Out-Host
Assert-True ($LASTEXITCODE -eq 0) "gen_jobs second run failed"
$m2 = Get-Content -LiteralPath $manifestA -Raw | ConvertFrom-Json
Assert-True ([int]$m2.counts.jobs_emitted -eq 0) "expected jobs_emitted=0 on second run"
Assert-True ([int]$m2.counts.jobs_skipped -eq 3) "expected jobs_skipped=3 on second run"

# 3) Stable filenames in different out-dir
$manifestB = Join-Path $outB "manifest.json"
$jobsB = Join-Path $outB "jobs.txt"
& $Py -m shorts_engine.layer2.cli.gen_jobs --input $csv --template $tpl --out-dir $outB --manifest-out $manifestB --jobs-file-out $jobsB | Out-Host
Assert-True ($LASTEXITCODE -eq 0) "gen_jobs out_b run failed"
$mB = Get-Content -LiteralPath $manifestB -Raw | ConvertFrom-Json
$namesA = @($m1.items | ForEach-Object { [System.IO.Path]::GetFileName([string]$_.job_path) })
$namesB = @($mB.items | ForEach-Object { [System.IO.Path]::GetFileName([string]$_.job_path) })
Assert-True (($namesA -join "|") -eq ($namesB -join "|")) "deterministic filenames mismatch between out dirs"

# 4) Optional quick batch run from generated jobs
& $Py -m shorts_engine.layer2.cli.render_batch --jobs-file $jobsB --max 1 | Out-Host
Assert-True (($LASTEXITCODE -eq 0) -or ($LASTEXITCODE -eq 2)) "render_batch on generated jobs unexpected exit code"

Remove-Item -Recurse -Force $tmp
Write-Host "OK: smoke_gen_jobs passed"
