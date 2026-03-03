param(
  [string]$RepoRoot = (git rev-parse --show-toplevel),
  [string]$Py = "python"
)

$ErrorActionPreference = "Stop"

function Assert-True($cond, $msg) { if (-not $cond) { throw "ASSERT FAIL: $msg" } }
function Parse-LastJson([string[]]$lines) {
  $last = $lines | Select-Object -Last 1
  return ($last | ConvertFrom-Json)
}

Write-Host "== smoke_ideas =="
Set-Location $RepoRoot

$tmp = Join-Path $RepoRoot "_junk\smoke_ideas"
$dataDir = Join-Path $tmp "data"
$inDir = Join-Path $tmp "in"
$outDir = Join-Path $tmp "jobs_out"
New-Item -ItemType Directory -Force $dataDir | Out-Null
New-Item -ItemType Directory -Force $inDir | Out-Null
New-Item -ItemType Directory -Force $outDir | Out-Null

# 1) add 2 ideas
$a1 = & $Py -m shorts_engine.layer2.cli.ideas --data-dir $dataDir add --topic "T1" --hook "Hook One" --body "Body One" --ending "End One" --tags "a,b" --lang "tr" --duration-sec 8
Assert-True ($LASTEXITCODE -eq 0) "ideas add #1 failed"
$j1 = Parse-LastJson -lines $a1
Assert-True ($j1.ok -eq $true) "ideas add #1 JSON not ok"

$a2 = & $Py -m shorts_engine.layer2.cli.ideas --data-dir $dataDir add --topic "T2" --hook "Hook Two" --body "Body Two" --ending "End Two" --tags "b,c" --lang "tr" --duration-sec 9
Assert-True ($LASTEXITCODE -eq 0) "ideas add #2 failed"
$j2 = Parse-LastJson -lines $a2
Assert-True ($j2.ok -eq $true) "ideas add #2 JSON not ok"

# 2) build-csv
$csvOut = Join-Path $inDir "inputs.csv"
$bc = & $Py -m shorts_engine.layer2.cli.ideas --data-dir $dataDir build-csv --out $csvOut --status queued
Assert-True ($LASTEXITCODE -eq 0) "ideas build-csv failed"
Assert-True (Test-Path -LiteralPath $csvOut) "inputs.csv missing"
$csvLines = Get-Content -LiteralPath $csvOut
Assert-True ($csvLines.Count -ge 3) "inputs.csv should have header + 2 rows"

# 3) gen_jobs from built csv
$tplPath = Join-Path $inDir "template.json"
$tplObj = @{
  version = "0.5"
  output = @{ path = "output/{{id}}.mp4" }
  video = @{ resolution = "1080x1920"; fps = 30; duration_sec = 8 }
  hook = "{{hook}}"
  pattern_break = "{{body}}"
  loop_ending = "{{ending}}"
  subtitles = @{ items = @(@{text="{{hook}}"}, @{text="{{body}}"}, @{text="{{ending}}"}) }
}
$tplObj | ConvertTo-Json -Depth 64 | Set-Content -LiteralPath $tplPath -Encoding utf8

$manifest = Join-Path $outDir "manifest.json"
$jobsTxt = Join-Path $outDir "jobs.txt"
$g = & $Py -m shorts_engine.layer2.cli.gen_jobs --input $csvOut --template $tplPath --out-dir $outDir --manifest-out $manifest --jobs-file-out $jobsTxt
Assert-True ($LASTEXITCODE -eq 0) "gen_jobs from ideas csv failed"
Assert-True (Test-Path -LiteralPath $manifest) "manifest missing"
Assert-True (Test-Path -LiteralPath $jobsTxt) "jobs.txt missing"
$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
Assert-True ($m.items.Count -eq 2) "manifest items expected 2"
$jl = Get-Content -LiteralPath $jobsTxt | Where-Object { $_ -and $_.Trim() -ne "" }
Assert-True ($jl.Count -eq 2) "jobs.txt lines expected 2"

# 4) optional quick render proof
& $Py -m shorts_engine.layer2.cli.render_batch --jobs-file $jobsTxt --max 1 | Out-Host
Assert-True (($LASTEXITCODE -eq 0) -or ($LASTEXITCODE -eq 2)) "render_batch quick proof unexpected exit"

Remove-Item -Recurse -Force $tmp
Write-Host "OK: smoke_ideas passed"
