param(
  [string] $Tag,
  [string] $Msg,
  [switch] $Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Tag)) {
  Write-Host "Usage: pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\release.ps1 -Tag vX.Y.Z -Msg `"release notes`""
  exit 2
}

if ([string]::IsNullOrWhiteSpace($Msg)) {
  $Msg = $Tag
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Resolve-Path -LiteralPath (Join-Path $ScriptDir "..")
Set-Location -LiteralPath $repo
. (Join-Path $ScriptDir "_pslib.ps1")

try {
  $porcelain = (Run "git" @("status", "--porcelain") | Out-String).TrimEnd()
  if (-not [string]::IsNullOrWhiteSpace($porcelain)) {
    Write-Host "RELEASE_BLOCKED: working tree is not clean"
    Write-Host $porcelain
    exit 2
  }

  $qaOutput = (Run "pwsh" @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ".\tools\qa_cli.ps1") | Out-String)
  if ($qaOutput -notmatch "(?m)^QA_PASS\s*$") {
    throw "QA script did not emit QA_PASS"
  }

  # Check tag existence intentionally without throwing.
  $nativeVar = Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope Global -ErrorAction SilentlyContinue
  $oldNative = $null
  if ($null -ne $nativeVar) {
    $oldNative = $global:PSNativeCommandUseErrorActionPreference
    $global:PSNativeCommandUseErrorActionPreference = $false
  }
  try {
    & git rev-parse -q --verify ("refs/tags/{0}" -f $Tag) *> $null
    $tagExists = ($LASTEXITCODE -eq 0)
  } finally {
    if ($null -ne $nativeVar) {
      $global:PSNativeCommandUseErrorActionPreference = $oldNative
    }
  }

  if ($tagExists -and -not $Force) {
    Write-Host ("RELEASE_BLOCKED: tag '{0}' already exists" -f $Tag)
    Write-Host "Pick a new tag and rerun (default safety: no overwrite)."
    Write-Host "Optional: rerun with -Force to recreate the local tag."
    exit 2
  }

  if ($tagExists -and $Force) {
    Run "git" @("tag", "-d", $Tag) | Out-Null
  }

  Run "git" @("tag", "-a", $Tag, "-m", $Msg) | Out-Null
  Write-Host ("TAG_CREATED {0}" -f $Tag)
  Write-Host "NEXT:"
  Write-Host "git push --tags"
  Write-Host "git push"
  exit 0
} catch {
  Write-Host ("RELEASE_FAIL: {0}" -f $_.Exception.Message)
  exit 2
}
