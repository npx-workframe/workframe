# Archive repo for VPS deploy — tracked + untracked (not gitignored) files.
param(
  [string]$OutPath = $(Join-Path $env:TEMP "workframe-working-tree.tar"),
  [string]$Root = $(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
)

$ErrorActionPreference = "Stop"
Push-Location $Root
try {
  $listFile = [IO.Path]::GetTempFileName()
  try {
    $files = @()
    $files += & git ls-files
    $files += & git ls-files --others --exclude-standard
    $files = $files | Where-Object { $_.Trim() -and (Test-Path (Join-Path $Root $_)) } | Sort-Object -Unique
    if (-not $files.Count) { throw "no files to pack under $Root" }
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($listFile, $files, $utf8NoBom)
    if (Test-Path $OutPath) { Remove-Item -Force $OutPath }
    & tar -cf $OutPath -T $listFile
    Write-Output $OutPath
  } finally {
    Remove-Item -Force $listFile -ErrorAction SilentlyContinue
  }
} finally {
  Pop-Location
}
