$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$config = Join-Path $Root 'Agents\config.yaml'
if (-not (Test-Path $config)) {
  throw @"
Hermes is not initialized in Agents/.
Run the full Phase B installer: .\scripts\start-install.ps1
Or run Hermes setup first, then re-run: .\scripts\install.ps1
"@
}

Write-Host "Bootstrapping Workframe Agent (workframe-agent)..."
& "$Root\scripts\bootstrap-native.ps1"
& "$Root\scripts\verify-bootstrap.ps1"

Write-Host 'Starting full stack (gateway, dashboard, workframe-api, Workframe UI)...'
docker compose up -d

Write-Host ''
Write-Host "Phase B complete - Workframe Agent is ready." -ForegroundColor Green
Write-Host '  Browser chat (TUI): http://127.0.0.1:18269/chat'
Write-Host '  Terminal chat: .\scripts\chat.ps1'
Write-Host '  Auth/UI surface: http://127.0.0.1:18644'
Write-Host '  Workframe UI: http://127.0.0.1:18270'
Write-Host '  Hermes ops dashboard: http://127.0.0.1:18269'
Write-Host '  Add specialists: .\scripts\add-profile.ps1 <slug>'
Write-Host ''
Write-Host 'Opening Workframe UI...' -ForegroundColor Green
& "$Root\scripts\open-workframe-ui.ps1"

