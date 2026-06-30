$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

New-Item -ItemType Directory -Force -Path Agents, Files | Out-Null

Write-Host ''
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ' Workframe Phase B - complete boot' -ForegroundColor Cyan
Write-Host " Project: Workframe Agent" -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Step 1/3 - Hermes setup (credentials, interactive)' -ForegroundColor Yellow
Write-Host '         Keys stay here - never paste in agent chat.' -ForegroundColor DarkGray
Write-Host ''

docker pull nousresearch/hermes-agent:latest
docker run --rm -it --name workframe-setup --entrypoint hermes `
  -v "$Root\Agents:/opt/data" `
  -v "$Root\Files:/workspace" `
  nousresearch/hermes-agent:latest setup

if ($LASTEXITCODE -ne 0) {
  Write-Host 'Hermes setup cancelled or failed.' -ForegroundColor Red
  Read-Host 'Press Enter to close'
  exit $LASTEXITCODE
}

Write-Host ''
Write-Host "Step 2/3 - Bootstrap Workframe Agent..." -ForegroundColor Yellow
& "$Root\scripts\bootstrap-native.ps1"
& "$Root\scripts\verify-bootstrap.ps1"

Write-Host ''
Write-Host 'Step 3/3 - Full stack (gateway, dashboard, workframe-api, Workframe UI)...' -ForegroundColor Yellow
docker compose up -d

Write-Host ''
Write-Host '========================================' -ForegroundColor Green
Write-Host " Phase B complete - Workframe Agent is ready" -ForegroundColor Green
Write-Host '========================================' -ForegroundColor Green
Write-Host ''
Write-Host '  Browser chat (TUI): http://127.0.0.1:18269/chat'
Write-Host '  Terminal chat:     .\scripts\chat.ps1'
Write-Host '  Auth/UI surface:   http://127.0.0.1:18644'
Write-Host '  Workframe UI:      http://127.0.0.1:18270'
Write-Host '  Hermes ops:        http://127.0.0.1:18269'
Write-Host ''
Write-Host ''
Write-Host 'Opening Workframe UI...' -ForegroundColor Green
& "$Root\scripts\open-workframe-ui.ps1"

Read-Host 'Press Enter to close'
