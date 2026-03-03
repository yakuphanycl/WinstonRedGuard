param(
  [Parameter(Mandatory=$true)][string]$RunDir,
  [string]$InVideo  = "video.mp4",
  [string]$OutVideo = "final.mp4",
  [string]$TextFile = "script.txt",
  [switch]$WriteMeta
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-InRunDir([string]$p) {
  if ([string]::IsNullOrWhiteSpace($p)) { throw "empty path" }
  if ([System.IO.Path]::IsPathRooted($p)) { return $p }
  return (Join-Path $RunDir $p)
}

function Try-Json($cmdArgs) {
  $out = & ffprobe @cmdArgs 2>$null
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($out)) { return $null }
  try { return ($out | ConvertFrom-Json) } catch { return $null }
}

$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent  # ...\pc_motor
$ttsMux   = Join-Path $repoRoot "shorts_engine\tools\tts_mux_qc.ps1"

$inAbs    = Resolve-InRunDir $InVideo
$outAbs   = Resolve-InRunDir $OutVideo
$textAbs  = Resolve-InRunDir $TextFile

$tsUtc = (Get-Date).ToUniversalTime().ToString("o")
$cwd   = (Get-Location).Path

$metaPath = Join-Path $RunDir "meta.json"
$diag = "ok"
$artifactsOk = $false

# Minimal meta scaffold
$meta = [ordered]@{
  ts_utc = $tsUtc
  cwd = $cwd
  cmd = @("powershell","-File",$MyInvocation.MyCommand.Path,"-RunDir",$RunDir,"-InVideo",$InVideo,"-OutVideo",$OutVideo,"-TextFile",$TextFile)  # approx
  diagnosis = $null
  artifacts_ok = $false
  requested = [ordered]@{
    in_video = $InVideo
    out_video = $OutVideo
    text_file = $TextFile
  }
  artifacts = [ordered]@{
    mp4_path = $outAbs
    mp4_exists = $false
    mp4_size_bytes = $null
  }
  probe = [ordered]@{
    format = $null
    streams = @()
  }
}

# Guard checks
if (-not (Test-Path -LiteralPath $ttsMux -PathType Leaf)) { $diag="missing_dependency"; throw "missing dependency: $ttsMux" }
if (-not (Test-Path -LiteralPath $inAbs -PathType Leaf))  { $diag="missing_input"; throw "missing InVideo: $inAbs" }
if (-not (Test-Path -LiteralPath $textAbs -PathType Leaf)) { $diag="missing_text"; throw "missing TextFile: $textAbs" }

# 1) Run mux+qc (tts_mux_qc already prints PASS/FAIL)
& powershell -NoProfile -ExecutionPolicy Bypass -File $ttsMux `
  -RunDir $RunDir `
  -InVideo (Split-Path $inAbs -Leaf) `
  -OutVideo (Split-Path $outAbs -Leaf) `
  -TextFile $textAbs

$rc = $LASTEXITCODE
if ($rc -ne 0) { $diag="mux_fail"; throw "run_qc_gate: tts_mux_qc failed rc=$rc" }
if (-not (Test-Path -LiteralPath $outAbs -PathType Leaf)) { $diag="missing_output"; throw "run_qc_gate: output missing: $outAbs" }

# 2) ffprobe: format+streams JSON
$probe = Try-Json @("-hide_banner","-v","error","-of","json","-show_format","-show_streams",$outAbs)

$meta.artifacts.mp4_exists = $true
$meta.artifacts.mp4_size_bytes = (Get-Item -LiteralPath $outAbs).Length

if ($null -eq $probe) {
  $diag="probe_fail"
} else {
  $meta.probe.format = $probe.format
  $meta.probe.streams = $probe.streams

  $hasVideo = $false
  $hasAudio = $false

  foreach ($s in $probe.streams) {
    if ($s.codec_type -eq "video") { $hasVideo = $true }
    if ($s.codec_type -eq "audio") { $hasAudio = $true }
  }

  if (-not $hasVideo) {
    $diag="no_video_stream"
  } elseif (-not $hasAudio) {
    $diag="no_audio_stream"
  } else {
    $diag="ok"
    $artifactsOk = $true
  }
}

$meta.diagnosis = $diag
$meta.artifacts_ok = $artifactsOk

if ($WriteMeta) {
  $meta | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $metaPath -Encoding UTF8
  Write-Host "[META] wrote -> $metaPath"
}

if (-not $artifactsOk) {
  Write-Host "[GATE FAIL] diagnosis=$diag out=$outAbs"
  exit 2
}

Write-Host "[GATE PASS] -> $outAbs"
exit 0
