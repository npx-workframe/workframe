# Full Playwright E2E against disposable slot 3 (DEV_LOCAL_UNSAFE).
# Prerequisite: .\scripts\workframe\e2e-slot3-up.ps1
param(
  [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$UiUrl = 'http://127.0.0.1:38644'
$ApiUrl = 'http://127.0.0.1:39120'

Write-Host "Checking E2E slot 3 API at $ApiUrl ..."
try {
  $health = Invoke-RestMethod -Uri "$ApiUrl/api/health" -TimeoutSec 5
} catch {
  Write-Host 'E2E stack not reachable. Start it first:'
  Write-Host '  .\scripts\workframe\e2e-slot3-up.ps1 -Fresh'
  exit 1
}

if ($health.mode -ne 'dev_unsafe') {
  Write-Host "Expected dev_unsafe mode; got $($health.mode). Use e2e-slot3-up.ps1 (DEV_LOCAL_UNSAFE=true)."
  exit 1
}

Set-Location $Root
$env:WORKFRAME_E2E = '1'
$env:WORKFRAME_E2E_UNSAFE = '1'
$env:WORKFRAME_E2E_MODE = 'trusted_team'
$env:WORKFRAME_E2E_URL = $UiUrl
$env:WORKFRAME_E2E_API_URL = $ApiUrl

Write-Host "E2E full suite UI=$UiUrl API=$ApiUrl mode=$($health.deployment_mode)"

if (-not $SkipInstall) {
  pnpm --filter @workframe/web exec playwright install chromium
}

pnpm --filter @workframe/web test:e2e -- e2e/deployment-modes.spec.ts e2e/authenticated-rbac.spec.ts
