# Dogfood reset = npx create-workframe on Docker. Period.
#
# Tears down any prior install at <InstallRoot>/<ProjectName>, stops legacy
# infra/compose/workframe if it is running (same port slots), then runs ONLY:
#   npx create-workframe <ProjectName> --out <InstallRoot>
#
# create-workframe scaffolds, pulls Hermes, and launches Phase B (start-install).
# No manual .env creds, no bootstrap scripts, no compose-up from this repo.
#
# OFF LIMITS: %LOCALAPPDATA%\hermes (host Hermes / AIbert)
#
# Usage:
#   .\scripts\workframe\reset-dogfood-docker.ps1 -WhatIf
#   .\scripts\workframe\reset-dogfood-docker.ps1 -Confirm
#   .\scripts\workframe\reset-dogfood-docker.ps1 -Confirm -ProjectName MyBusiness -InstallRoot C:\projects
#
param(
  [string]$ProjectName = 'MyBusiness',
  [string]$InstallRoot = '',
  [switch]$WhatIf,
  [switch]$Confirm
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $InstallRoot) {
  $InstallRoot = (Resolve-Path (Join-Path $Root '..')).Path
}
$InstallRoot = (Resolve-Path $InstallRoot).Path
$Target = Join-Path $InstallRoot $ProjectName
$LegacyCompose = Join-Path $Root 'infra\compose\workframe'
$CreatePkg = Join-Path $Root 'packages\create-workframe'
$LocalHermes = Join-Path $env:LOCALAPPDATA 'hermes'

function Assert-NotHostHermes([string]$Path) {
  if (-not (Test-Path $Path)) { return }
  $item = Get-Item $Path -Force -ErrorAction SilentlyContinue
  if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
    $junctionTarget = ($item.Target | Out-String).ToLowerInvariant()
    if ($junctionTarget -match 'hermes|localappdata') {
      throw "Refusing: $Path is a junction toward host Hermes"
    }
  }
  $resolved = (Resolve-Path $Path -ErrorAction SilentlyContinue).Path.ToLowerInvariant()
  $hermes = $LocalHermes.ToLowerInvariant()
  if ($resolved -and ($resolved -eq $hermes -or $resolved.StartsWith($hermes + '\'))) {
    throw "Refusing: $Path resolves under host Hermes ($LocalHermes)"
  }
}

function Compose-Down([string]$Dir) {
  if (-not (Test-Path (Join-Path $Dir 'docker-compose.yml'))) { return }
  Push-Location $Dir
  $prevEap = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  docker compose down -v --remove-orphans 2>&1 | Out-Null
  $ErrorActionPreference = $prevEap
  Pop-Location
}

if (-not $WhatIf -and -not $Confirm) {
  Write-Host @"
Dogfood reset requires -Confirm (or -WhatIf to preview).

Dogfood reset = npx create-workframe on Docker only.
Default install: $Target

This script:
  - stops legacy infra/compose/workframe (if running)
  - removes the prior $ProjectName install directory
  - runs npx create-workframe (Phase B installer launches from the package)

This script does NOT touch:
  - repository source (services, apps, packages)
  - %LOCALAPPDATA%\hermes (host Hermes ? off limits)

"@
  exit 1
}

Assert-NotHostHermes $Target

$pkgVersion = 'unknown'
$pkgJson = Join-Path $CreatePkg 'package.json'
if (Test-Path $pkgJson) {
  $pkgVersion = (Get-Content $pkgJson -Raw | ConvertFrom-Json).version
}

Write-Host '=== Dogfood reset plan ==='
Write-Host "  STOP    legacy compose: $LegacyCompose"
Write-Host "  REMOVE  $Target"
Write-Host "  RUN     npx create-workframe@$pkgVersion $ProjectName --out $InstallRoot"
Write-Host "  KEEP    $Root (source)"
Write-Host "  KEEP    $LocalHermes (host Hermes)"
Write-Host ''

if ($WhatIf) {
  Write-Host 'WhatIf: no changes made.'
  exit 0
}

if (-not (Test-Path (Join-Path $CreatePkg 'bin\create-workframe.js'))) {
  throw "Missing installer package at $CreatePkg"
}

Write-Host '=== stop legacy infra/compose/workframe (free ports) ==='
Compose-Down $LegacyCompose

Write-Host "=== remove prior $ProjectName install ==="
Compose-Down $Target
if (Test-Path $Target) {
  Remove-Item -Recurse -Force $Target
}

Write-Host '=== npx create-workframe (only step ? package owns bootstrap + docker) ==='
Push-Location $InstallRoot
try {
  npx --yes --package="$CreatePkg" create-workframe $ProjectName --out $InstallRoot --deploy docker
  if ($LASTEXITCODE -ne 0) { throw "npx create-workframe failed ($LASTEXITCODE)" }
}
finally {
  Pop-Location
}

if (-not (Test-Path (Join-Path $Target 'docker-compose.yml'))) {
  throw "Install missing after create-workframe: $Target"
}

$uiPort = '18644'
$apiPort = '19120'
$envPath = Join-Path $Target '.env'
if (Test-Path $envPath) {
  $uiLine = Select-String -Path $envPath -Pattern '^WORKFRAME_UI_PORT=' | Select-Object -Last 1
  $apiLine = Select-String -Path $envPath -Pattern '^WORKFRAME_API_PORT=' | Select-Object -Last 1
  if ($uiLine) { $uiPort = $uiLine.Line.Split('=', 2)[1].Trim() }
  if ($apiLine) { $apiPort = $apiLine.Line.Split('=', 2)[1].Trim() }
}

Write-Host ''
Write-Host 'Dogfood reset complete ? finish setup in the browser (wizard), or it did not boot.'
Write-Host "  Install dir  $Target"
Write-Host "  UI           http://127.0.0.1:$uiPort/"
Write-Host "  API health   http://127.0.0.1:$apiPort/api/health"
