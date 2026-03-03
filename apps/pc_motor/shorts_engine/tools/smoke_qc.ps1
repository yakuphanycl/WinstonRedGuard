param(
  [Parameter(Mandatory=$false)][string]$Job = "shorts_engine\layer2\jobs\_min_test_job_tts.json",
  [Parameter(Mandatory=$false)][double]$MaxDriftSec = 0.35
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = "C:\dev\pc_motor"
Set-Location $repo

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$log = Join-Path $repo "runs\_smoke_qc_$ts.log"

python -m shorts_engine.layer2.cli.render_job --job $Job *>> $log
$rc = $LASTEXITCODE

"rc=$rc log=$log"
if ($rc -ne 0) {
  Write-Host "FAIL: render_job rc=$rc"
  Get-Content -LiteralPath $log -Tail 140
  exit 10
}

# run_id çıkar
$runId = $null
$tail = Get-Content -LiteralPath $log -Tail 220
foreach ($ln in $tail) {
  if ($ln -match 'run_id=([0-9a-f]{12})') { $runId = $matches[1] }
}
if (-not $runId) {
  Write-Host "FAIL: run_id not found in log"
  Get-Content -LiteralPath $log -Tail 140
  exit 11
}

$runDir = Join-Path $repo ("runs\" + $runId)
$final  = Join-Path $runDir "final.mp4"
$tts    = Join-Path $runDir "tts.mp3"
$meta   = Join-Path $runDir "meta.json"

if (-not (Test-Path -LiteralPath $final -PathType Leaf)) {
  Write-Host "FAIL: final.mp4 missing: $final"
  exit 20
}

# FINAL duration
$finalDur = [double](& ffprobe -hide_banner -v error -show_entries format=duration -of default=nw=1:nk=1 $final)
if (-not $finalDur) { throw "ffprobe final duration failed" }

# Audio stream var mı?
$probeFinal = & ffprobe -hide_banner -v error `
  -show_entries stream=codec_type,codec_name,channels,sample_rate:format=duration `
  -of json $final | Out-String

$hasAudio = $false
if ($probeFinal -match '"codec_type"\s*:\s*"audio"') { $hasAudio = $true }

# TTS duration (tts.mp3 varsa)
$ttsDur = $null
if (Test-Path -LiteralPath $tts -PathType Leaf) {
  $ttsDur = [double](& ffprobe -hide_banner -v error -show_entries format=duration -of default=nw=1:nk=1 $tts)
}

# Drift hesapla (tts varsa)
$drift = $null
$driftOk = $true
if ($ttsDur -ne $null -and $ttsDur -gt 0) {
  $drift = [math]::Abs($ttsDur - $finalDur)
  if ($drift -gt $MaxDriftSec) { $driftOk = $false }
}

Write-Host "RUN=$runDir"
Write-Host "FINAL=$final"
Write-Host ("FINAL_DUR_SEC=" + $finalDur)
Write-Host ("TTS_DUR_SEC=" + ($ttsDur -as [string]))
Write-Host ("DRIFT_SEC=" + ($drift -as [string]) + " (max=" + $MaxDriftSec + ")")
Write-Host "HAS_AUDIO=$hasAudio"
Write-Host $probeFinal

# meta.json'a QC yaz (varsa merge, yoksa yeni)
$qcObj = [ordered]@{
  has_audio   = $hasAudio
  final_dur_s = $finalDur
  tts_dur_s   = $ttsDur
  drift_s     = $drift
  drift_ok    = $driftOk
  max_drift_s = $MaxDriftSec
  artifacts_ok = ($hasAudio -and $driftOk)
  ts = (Get-Date).ToString("s")
}

try {
  $metaObj = $null
  if (Test-Path -LiteralPath $meta) {
    $metaObj = Get-Content -LiteralPath $meta -Raw | ConvertFrom-Json
  } else {
    $metaObj = [pscustomobject]@{}
  }

  # qc alanını set et
  $metaObj | Add-Member -NotePropertyName "qc" -NotePropertyValue $qcObj -Force

  ($metaObj | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $meta -Encoding UTF8
  Write-Host "WROTE_META_QC=$meta"
} catch {
  Write-Host "WARN: meta.json qc write failed: $($_.Exception.Message)"
}

if (-not $hasAudio) {
  Write-Host "FAIL: no audio stream"
  exit 30
}

if (-not $driftOk) {
  Write-Host "FAIL: drift too high"
  exit 31
}

Write-Host "OK: artifacts_ok=true"
exit 0