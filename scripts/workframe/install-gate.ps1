# Installer sign-off gate — canonical source → pack → scaffold smoke.
# Usage: .\scripts\workframe\install-gate.ps1 [-Quick]
param([switch]$Quick)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Pkg = Join-Path $Root 'packages\create-workframe'
$GateDir = Join-Path $Root '.install-gate'

Set-Location $Root
Write-Host 'OK: building web'
pnpm build:web
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
$packOut = npm pack --pack-destination $GateDir 2>&1
if ($LASTEXITCODE -ne 0) { throw "npm pack failed: $packOut" }
$tgz = ($packOut | Select-String '\.tgz$' | Select-Object -Last 1).Line.Trim()
if (-not $tgz) { throw 'npm pack did not produce tarball' }
$archive = Join-Path $GateDir $tgz
foreach ($path in @('package/scripts/lib/install-identity.mjs', 'package/scripts/bootstrap-workspace-link.sh')) {
    $hit = tar -tzf $archive | Select-String -SimpleMatch $path
    if (-not $hit) { throw "pack missing $path" }
}
Write-Host 'OK: pack contains installer scripts'

if (-not $Quick -and (Test-Path (Join-Path $Root 'infra\compose\workframe\.env'))) {
    & bash (Join-Path $Root 'scripts\workframe\verify-public-deploy.sh') (Join-Path $Root 'infra\compose\workframe')
    if ($LASTEXITCODE -ne 0) { throw 'verify-public-deploy failed' }
    Write-Host 'OK: verify-public-deploy'
} else {
    Write-Host 'OK: skipping verify-public-deploy (-Quick or no compose .env)'
}

Write-Host 'OK: install gate passed'
