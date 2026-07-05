# Run Playwright deployment-mode security tests against a running Docker stack.
# Prerequisite: generated dogfood (reset-dogfood-docker.ps1 -Confirm) @ 127.0.0.1:18644 / API 19120
#
# Other modes: set WORKFRAME_DEPLOYMENT_MODE in ../MyBusiness/.env, recreate API, then:
#   $env:WORKFRAME_E2E_MODE = 'public_multi_user'
#   powershell -File scripts/workframe/run-e2e-deployment-modes.ps1
param(
  [string]$Mode = $env:WORKFRAME_E2E_MODE,
  [string]$UiUrl = $env:WORKFRAME_E2E_URL,
  [string]$ApiUrl = $env:WORKFRAME_E2E_API_URL
)

$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
if (-not $Mode) { $Mode = 'trusted_team' }
if (-not $UiUrl) { $UiUrl = 'http://127.0.0.1:18644' }
if (-not $ApiUrl) { $ApiUrl = 'http://127.0.0.1:19120' }

Set-Location $Root
$env:WORKFRAME_E2E = '1'
$env:WORKFRAME_E2E_MODE = $Mode
$env:WORKFRAME_E2E_URL = $UiUrl
$env:WORKFRAME_E2E_API_URL = $ApiUrl

Write-Host "E2E deployment_mode=$Mode UI=$UiUrl API=$ApiUrl"
pnpm --filter @workframe/web exec playwright install chromium
pnpm --filter @workframe/web test:e2e -- e2e/deployment-modes.spec.ts
