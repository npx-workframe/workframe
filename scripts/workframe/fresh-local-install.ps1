# Wipe local Workframe runtime + DB, bootstrap one Hermes profile, start compose.
param(
  [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$Compose = Join-Path $Root 'infra\compose\workframe'
$ApiData = Join-Path $Root 'runtime\workframe-api-data'
$Seed = Join-Path $Root 'scripts\workframe\seed\profiles\workframe-agent'

Write-Host '=== docker compose down ==='
Push-Location $Compose
docker compose down --remove-orphans
Pop-Location

Write-Host '=== wipe API data ==='
if (Test-Path $ApiData) {
  Remove-Item -Recurse -Force (Join-Path $ApiData '*') -ErrorAction SilentlyContinue
}

Write-Host '=== fresh runtime Agents/Files ==='
& (Join-Path $Root 'scripts\workframe\isolate-local-runtime.ps1') -Fresh

Write-Host '=== bootstrap workframe-agent profile ==='
$rtAgents = Join-Path $Root 'runtime\Agents'
$rtFiles = Join-Path $Root 'runtime\Files'
$profileDir = Join-Path $rtAgents 'profiles\workframe-agent'
if (Test-Path $profileDir) {
  Remove-Item -Recurse -Force $profileDir
}
docker run --rm --entrypoint hermes `
  -v "${rtAgents}:/opt/data" `
  -v "${rtFiles}:/workspace" `
  nousresearch/hermes-agent:latest `
  profile create workframe-agent --clone --description "Workframe native agent"
if ($LASTEXITCODE -ne 0) { Write-Host "profile create exit $LASTEXITCODE (may already exist)" }
if (Test-Path (Join-Path $Seed 'SOUL.md')) {
  Copy-Item (Join-Path $Seed 'SOUL.md') (Join-Path $rtAgents 'profiles\workframe-agent\SOUL.md') -Force
}
& (Join-Path $PSScriptRoot 'bootstrap-native-profile.ps1') -AgentsRoot $rtAgents

if (-not $SkipBuild) {
  Write-Host '=== build web ==='
  Push-Location $Root
  pnpm build:web
  Pop-Location
}

Write-Host '=== docker compose up ==='
Push-Location $Compose
docker compose up -d --build
Pop-Location

Write-Host ''
Write-Host 'Fresh install ready:'
Write-Host '  UI   http://127.0.0.1:18644/'
Write-Host '  API  http://127.0.0.1:19120/api/health'
Write-Host '  Step 1: sign in (OTP) -> Step 2: admin onboarding wizard -> Step 3: invite member'
Write-Host '  Safer wipe: .\scripts\workframe\reset-dogfood-docker.ps1 -WhatIf'
