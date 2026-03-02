param(
  [Parameter(Mandatory=$true)][string]$Path,
  [Parameter(Mandatory=$true)][string]$Text
)

$enc = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($Path, $Text, $enc)
