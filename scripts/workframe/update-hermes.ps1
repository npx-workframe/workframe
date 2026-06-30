$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host 'Pulling latest Hermes image...'
docker compose pull gateway dashboard
Write-Host 'Recreating Hermes containers (in-container hermes update is unsupported in Docker)...'
docker compose up -d --force-recreate gateway dashboard
Write-Host 'Done. Workframe API and Workframe UI remain in place unless you recreate the full stack.'
