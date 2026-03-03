# tools/gen_apps_index.ps1

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$appsDir  = Join-Path $repoRoot "apps"
$readme   = Join-Path $repoRoot "README.md"

if (!(Test-Path $appsDir)) {
  Write-Error "apps/ directory not found"
  exit 1
}

$apps = Get-ChildItem $appsDir -Directory | Sort-Object Name

$rows = foreach ($a in $apps) {

  $name = $a.Name
  $root = $a.FullName

  $pyproject = Test-Path (Join-Path $root "pyproject.toml")
  $tests     = Test-Path (Join-Path $root "tests")

  $tier = if ($pyproject -and $tests) { "release" }
          elseif ($tests)             { "workspace" }
          else                        { "legacy" }

  "| $name | $tier |"
}

$table = @()
$table += "| App | Tier |"
$table += "|-----|------|"
$table += $rows

$block = $table -join "`n"

$start = "<!-- WRG:APPS_START -->"
$end   = "<!-- WRG:APPS_END -->"

if (!(Test-Path $readme)) {
  Write-Host "README.md not found. Creating new one."
  $content = @"
# WinstonRedGuard

## Apps

$start
$block
$end
"@
  $content | Set-Content $readme -Encoding UTF8
  exit 0
}

$text = Get-Content $readme -Raw

# --- WRG: marker guard ---
if ($text -notmatch '<!--\s*WRG:APPS_START\s*-->' -or $text -notmatch '<!--\s*WRG:APPS_END\s*-->') {
  throw "README.md is missing WRG markers: <!-- WRG:APPS_START --> / <!-- WRG:APPS_END -->"
}

if ($text -match [regex]::Escape($start)) {

  $pattern = "(?s)$([regex]::Escape($start)).*?$([regex]::Escape($end))"
  $replacement = "$start`n$block`n$end"

  $text = [regex]::Replace($text, $pattern, $replacement)

} else {

  $text += "`n## Apps`n`n$start`n$block`n$end`n"
}

# --- WRG: idempotent README write ---
$old = Get-Content -LiteralPath $readme -Raw -Encoding UTF8

if ($old -ne $text) {
  $text | Set-Content -LiteralPath $readme -Encoding UTF8
  Write-Host "README apps index updated."
} else {
  Write-Host "README apps index already up-to-date."
}


