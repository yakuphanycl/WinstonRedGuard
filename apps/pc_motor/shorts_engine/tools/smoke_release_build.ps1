param(
  [string]$RepoRoot = (git rev-parse --show-toplevel),
  [string]$Py = "python"
)

$ErrorActionPreference = "Stop"

function Assert-True($cond, $msg) {
  if (-not $cond) { throw "ASSERT FAIL: $msg" }
}

Write-Host "== smoke_release_build =="
Set-Location $RepoRoot

$s1 = & $Py -m shorts_engine.layer2.cli.release status
Assert-True ($LASTEXITCODE -eq 0) "release status failed"
$j1 = $s1 | Select-Object -Last 1 | ConvertFrom-Json
Assert-True ($j1.ok -eq $true) "release status JSON ok=false"
Assert-True ($j1.version) "release status missing version"

# Avoid recursion when called from release_check gate.
$s2 = & $Py -m shorts_engine.layer2.cli.release build --skip-gates
Assert-True ($LASTEXITCODE -eq 0) "release build failed"
$j2 = $s2 | Select-Object -Last 1 | ConvertFrom-Json
Assert-True ($j2.ok -eq $true) "release build JSON ok=false"
Assert-True ($j2.zip_path) "release build missing zip_path"
Assert-True ($j2.manifest_path) "release build missing manifest_path"

$zipPath = Join-Path $RepoRoot $j2.zip_path
$manifestPath = Join-Path $RepoRoot $j2.manifest_path
Assert-True (Test-Path -LiteralPath $zipPath) "zip not found: $zipPath"
Assert-True (Test-Path -LiteralPath $manifestPath) "manifest not found: $manifestPath"

$m = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
Assert-True ($m.version) "manifest.version missing"
Assert-True ($m.artifacts.zip_sha256) "manifest missing zip_sha256"
Assert-True ($m.artifacts.manifest_sha256) "manifest missing manifest_sha256"

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
try {
  $entries = @($zip.Entries | ForEach-Object { $_.FullName })
  Assert-True ($entries.Count -gt 0) "zip has no entries"

  $bad = $entries | Where-Object { $_ -match '(^|/)runs/' -or $_ -match '(^|/)output/' }
  Assert-True ($bad.Count -eq 0) "zip contains forbidden runs/output paths"

  $hasLayer2 = ($entries | Where-Object { $_ -like "shorts_engine/layer2/*" }).Count -gt 0
  $hasTools = ($entries | Where-Object { $_ -like "shorts_engine/tools/*" }).Count -gt 0
  $hasDocs = ($entries | Where-Object { $_ -like "shorts_engine/docs/*" }).Count -gt 0
  Assert-True $hasLayer2 "zip missing layer2 files"
  Assert-True $hasTools "zip missing tools files"
  Assert-True $hasDocs "zip missing docs files"
}
finally {
  $zip.Dispose()
}

Write-Host "OK: smoke_release_build passed"

