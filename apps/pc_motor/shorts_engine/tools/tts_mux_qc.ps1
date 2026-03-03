param(
  [Parameter(Mandatory=$true)][string]$RunDir,
  [Parameter(Mandatory=$true)][string]$InVideo,
  [Parameter(Mandatory=$true)][string]$OutVideo,
  [Parameter(Mandatory=$false)][string]$Text,
  [Parameter(Mandatory=$false)][string]$TextFile,
  [Parameter(Mandatory=$false)][string]$Voice = "tr-TR-EmelNeural",
  [Parameter(Mandatory=$false)][string]$Rate  = "-5%",
  [Parameter(Mandatory=$false)][string]$Volume = "+0%",
  [Parameter(Mandatory=$false)][switch]$KeepTts
)

# UTF-8 hygiene (best-effort)
try { chcp 65001 | Out-Null; $OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new() } catch { }

function Die([string]$msg) { Write-Host "FAIL: $msg"; exit 1 }

if (-not (Test-Path -LiteralPath $RunDir -PathType Container)) { Die "RunDir yok: $RunDir" }

$inVid  = Join-Path $RunDir $InVideo
$outMp4 = Join-Path $RunDir $OutVideo
$ttsMp3 = Join-Path $RunDir "tts.mp3"

if (-not (Test-Path -LiteralPath $inVid -PathType Leaf)) { Die "Input video yok: $inVid" }

if (-not (Get-Command edge-tts -ErrorAction SilentlyContinue)) { Die "edge-tts yok (PATH/pip)" }
if (-not (Get-Command ffmpeg   -ErrorAction SilentlyContinue)) { Die "ffmpeg yok (PATH)" }
if (-not (Get-Command ffprobe  -ErrorAction SilentlyContinue)) { Die "ffprobe yok (PATH)" }

# Text resolve
if ([string]::IsNullOrWhiteSpace($Text)) {
  if (-not [string]::IsNullOrWhiteSpace($TextFile)) {
    if ([System.IO.Path]::IsPathRooted($TextFile)) {
      $tf = [System.IO.Path]::GetFullPath($TextFile)
    } else {
      if ([System.IO.Path]::IsPathRooted($TextFile)) {
        $tf = [System.IO.Path]::GetFullPath($TextFile)
      } else {
        $tf = Join-Path $RunDir $TextFile
      }
    }
    if (-not (Test-Path -LiteralPath $tf -PathType Leaf)) { Die "TextFile yok: $tf" }
    $Text = (Get-Content -LiteralPath $tf -Raw)
  }
}
if ($null -eq $Text) { $Text = "" }
$Text = $Text.Trim()
if ([string]::IsNullOrWhiteSpace($Text)) { Die "Text boÅŸ (Text veya TextFile ver)" }

Remove-Item -LiteralPath $ttsMp3 -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $outMp4 -Force -ErrorAction SilentlyContinue

Write-Host "[TTS] -> $ttsMp3"
& edge-tts --voice $Voice "--rate=$Rate" "--volume=$Volume" --text $Text --write-media $ttsMp3
if ($LASTEXITCODE -ne 0) { Die "edge-tts fail rc=$LASTEXITCODE" }
if (-not (Test-Path -LiteralPath $ttsMp3 -PathType Leaf)) { Die "tts.mp3 oluÅŸmadÄ±" }

Write-Host "[MUX] -> $outMp4"
ffmpeg -y -hide_banner -i $inVid -i $ttsMp3 -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 96k -ar 48000 -ac 1 -shortest -movflags +faststart $outMp4
if ($LASTEXITCODE -ne 0) { Die "ffmpeg fail rc=$LASTEXITCODE" }
if (-not (Test-Path -LiteralPath $outMp4 -PathType Leaf)) { Die "out mp4 oluşmadı" }

Write-Host "[QC] audio stream kontrol"
$probe = ffprobe -hide_banner -v error -show_entries stream=codec_type -of json $outMp4 | ConvertFrom-Json
$hasAudio = $probe.streams | Where-Object { $_.codec_type -eq "audio" } | Select-Object -First 1
if (-not $hasAudio) { Die "QC FAIL: audio stream yok" }

if (-not $KeepTts) { Remove-Item -LiteralPath $ttsMp3 -Force -ErrorAction SilentlyContinue }

Write-Host "[PASS] -> $outMp4"
exit 0



