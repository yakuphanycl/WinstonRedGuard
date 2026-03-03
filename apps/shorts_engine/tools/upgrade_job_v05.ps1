param(
  [Parameter(Mandatory=$true)][string]$In,
  [Parameter(Mandatory=$true)][string]$Out
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $In)) {
  throw "missing input: $In"
}

$inPath = (Resolve-Path -LiteralPath $In).Path
$outFull = [System.IO.Path]::GetFullPath($Out)
$outDir = Split-Path -Parent $outFull
if (-not [string]::IsNullOrWhiteSpace($outDir)) {
  New-Item -ItemType Directory -Force -Path $outDir | Out-Null
}

$j = Get-Content -LiteralPath $inPath -Raw | ConvertFrom-Json
$j.version = "0.5"

if (-not $j.hook)          { $j | Add-Member NoteProperty hook          "..." -Force }
if (-not $j.pattern_break) { $j | Add-Member NoteProperty pattern_break "..." -Force }
if (-not $j.loop_ending)   { $j | Add-Member NoteProperty loop_ending   "..." -Force }

if (-not $j.output)        { $j | Add-Member NoteProperty output (@{}) -Force }
if (-not $j.output.path)   { $j.output | Add-Member NoteProperty path "output/test.mp4" -Force }

if (-not $j.video)               { $j | Add-Member NoteProperty video (@{}) -Force }
if (-not $j.video.resolution)    { $j.video | Add-Member NoteProperty resolution "1080x1920" -Force }
if (-not $j.video.fps)           { $j.video | Add-Member NoteProperty fps 30 -Force }
if (-not $j.video.duration_sec)  { $j.video | Add-Member NoteProperty duration_sec 8 -Force }

if (-not $j.subtitles)      { $j | Add-Member NoteProperty subtitles (@{}) -Force }
if (-not $j.subtitles.items) {
  $j.subtitles | Add-Member NoteProperty items @(
    @{ text = $j.hook },
    @{ text = $j.pattern_break },
    @{ text = $j.loop_ending }
  ) -Force
}

$json = $j | ConvertTo-Json -Depth 64
[System.IO.File]::WriteAllText($outFull, $json, [System.Text.UTF8Encoding]::new($false))
Write-Host "OK: wrote $outFull"
