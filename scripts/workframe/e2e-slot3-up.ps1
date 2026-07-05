# Disposable E2E slot 3 — DEV_LOCAL_UNSAFE @ 127.0.0.1:38644.
# Playwright CI harness only — uses reference compose overlay, NOT dogfood (MyBusiness slot 1).
# Dogfood reset: reset-dogfood-docker.ps1 -Confirm
#
# Usage:
#   .\scripts\workframe\e2e-slot3-up.ps1              # up (bootstrap runtime if missing)
#   .\scripts\workframe\e2e-slot3-up.ps1 -Fresh      # wipe e2e-slot3 runtime + fresh bootstrap
#   .\scripts\workframe\e2e-slot3-up.ps1 -Down        # stop e2e containers only
#
param(
  [switch]$Fresh,
  [switch]$Down,
  [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Runtime = Join-Path $Root 'runtime\e2e-slot3'
$Agents = Join-Path $Runtime 'Agents'
$Files = Join-Path $Runtime 'Files'
$ApiData = Join-Path $Runtime 'workframe-api-data'
$Compose = Join-Path $Root 'infra\compose\workframe'
$EnvExample = Join-Path $Compose '.env.e2e-slot3.example'
$EnvFile = Join-Path $Compose '.env.e2e-slot3'
$ComposeArgs = @(
  '-f', (Join-Path $Compose 'docker-compose.yml'),
  '-f', (Join-Path $Compose 'docker-compose.e2e-slot3.yml'),
  '--env-file', $EnvFile
)

function Ensure-E2eEnvFile {
  if (Test-Path $EnvFile) { return }
  if (-not (Test-Path $EnvExample)) {
    throw "Missing $EnvExample"
  }
  $token = python -c "import secrets; print(secrets.token_hex(24))"
  if ($LASTEXITCODE -ne 0) {
    $token = -join ((1..48) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
  }
  $content = (Get-Content $EnvExample -Raw).Replace('change-me-e2e-supervisor', $token)
  Set-Content -Path $EnvFile -Value $content -NoNewline
  Write-Host "Created $EnvFile"
}

function Bootstrap-AgentProfile {
  $Seed = Join-Path $Root 'scripts\workframe\seed\profiles\workframe-agent'
  Write-Host '=== bootstrap workframe-agent in e2e-slot3 runtime ==='
  docker run --rm --entrypoint hermes `
    -v "${Agents}:/opt/data" `
    -v "${Files}:/workspace" `
    nousresearch/hermes-agent:latest `
    profile create workframe-agent --clone --description "Workframe E2E agent"
  if (Test-Path (Join-Path $Seed 'SOUL.md')) {
    Copy-Item (Join-Path $Seed 'SOUL.md') (Join-Path $Agents 'profiles\workframe-agent\SOUL.md') -Force
  }
}

function Wipe-E2eRuntime {
  Write-Host '=== wipe runtime/e2e-slot3 ==='
  if (Test-Path $Agents) { Remove-Item -Recurse -Force $Agents }
  if (Test-Path $Files) { Remove-Item -Recurse -Force $Files }
  if (Test-Path $ApiData) { Remove-Item -Recurse -Force (Join-Path $ApiData '*') -ErrorAction SilentlyContinue }
  New-Item -ItemType Directory -Force -Path $Files, (Join-Path $Agents 'profiles'), $ApiData | Out-Null
  $readme = @"
# WorkframeE2E

Disposable Playwright E2E runtime (slot 3).
"@
  Set-Content -Path (Join-Path $Files 'README.md') -Value $readme
}

Push-Location $Compose
try {
  if ($Down) {
    docker compose @ComposeArgs down --remove-orphans
    Write-Host 'E2E slot 3 stack stopped.'
    exit 0
  }

  Ensure-E2eEnvFile

  if ($Fresh) {
    docker compose @ComposeArgs down --remove-orphans 2>&1 | Out-Null
    Wipe-E2eRuntime
  }

  if (-not (Test-Path (Join-Path $Agents 'profiles\workframe-agent'))) {
    if (-not (Test-Path $Agents)) {
      New-Item -ItemType Directory -Force -Path $Files, (Join-Path $Agents 'profiles'), $ApiData | Out-Null
      Set-Content -Path (Join-Path $Files 'README.md') -Value '# WorkframeE2E'
    }
    Bootstrap-AgentProfile
  }

  if (-not $SkipBuild) {
    Push-Location $Root
    pnpm build:web
    Pop-Location
  }

  Write-Host '=== docker compose up (e2e slot 3) ==='
  docker compose @ComposeArgs up -d --build

  Write-Host ''
  Write-Host 'E2E slot 3 ready:'
  Write-Host '  UI   http://127.0.0.1:38644'
  Write-Host '  API  http://127.0.0.1:39120'
  Write-Host '  Run:  .\scripts\workframe\run-e2e-full.ps1'
}
finally {
  Pop-Location
}
