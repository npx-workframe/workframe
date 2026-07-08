# Installer sign-off gate — canonical source → pack.
# Dogfood install = reset-dogfood-docker.ps1 (npx create-workframe only).
# Usage: .\scripts\workframe\install-gate.ps1 [-Quick]
param([switch]$Quick)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Pkg = Join-Path $Root 'packages\create-workframe'
$GateDir = Join-Path $Root '.install-gate'

Set-Location $Root
Write-Host 'OK: building web'
$prevEapBuild = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
pnpm build:web
if ($LASTEXITCODE -ne 0) { throw "pnpm build:web failed ($LASTEXITCODE)" }
$ErrorActionPreference = $prevEapBuild
Write-Host 'OK: syncing API/supervisor to installer package'
node (Join-Path $Pkg 'scripts\sync-canonical-to-package.mjs')
Write-Host 'OK: bundling UI into installer package'
node (Join-Path $Pkg 'scripts\bundle-workframe-ui.mjs')
Write-Host 'OK: API tests'
pnpm test:api
Write-Host 'OK: installer scaffold tests'
pnpm test:scaffold

New-Item -ItemType Directory -Force -Path $GateDir | Out-Null
Set-Location $Pkg
$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$packOut = npm pack --pack-destination $GateDir 2>&1
$packExit = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($packExit -ne 0) { throw "npm pack failed: $packOut" }
$tgz = ($packOut | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ -match '^create-workframe-[\d.]+\.tgz$' } | Select-Object -Last 1)
if (-not $tgz) {
  $notice = ($packOut | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ -match 'filename:\s*create-workframe-[\d.]+\.tgz$' } | Select-Object -Last 1)
  if ($notice -match 'filename:\s*(create-workframe-[\d.]+\.tgz)$') { $tgz = $Matches[1] }
}
if (-not $tgz) { throw 'npm pack did not produce tarball name' }
$archive = Join-Path $GateDir $tgz
foreach ($path in @('package/scripts/lib/install-identity.mjs', 'package/scripts/bootstrap-workspace-link.sh')) {
    $hit = tar -tzf $archive | Select-String -SimpleMatch $path
    if (-not $hit) { throw "pack missing $path" }
}
$bootstrap = tar -xOf $archive package/scripts/bootstrap-workspace-link.sh
if ($bootstrap -match "`r") { throw 'pack bootstrap-workspace-link.sh has CRLF (Alpine sh will fail)' }
Write-Host 'OK: pack contains installer scripts (LF shell scripts)'

Write-Host 'OK: package install evidence'
node (Join-Path $Root 'scripts\workframe\run-package-install-evidence.mjs') --skip-prep
if ($LASTEXITCODE -ne 0) { throw 'package install evidence failed' }

Write-Host 'OK: install gate passed'
