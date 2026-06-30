# Reset DOCKER DOGFOOD only — runtime/ + workframe.db. Never touches source or host Hermes.
#
# SAFE TO DELETE (this script only):
#   runtime/Agents/              → Docker Hermes /opt/data (dogfood)
#   runtime/Files/               → Docker /workspace (dogfood artifacts)
#   runtime/workframe-api-data/  → auth.db + workframe.db
#   %LOCALAPPDATA%\hermes  (local AIbert / host Hermes)
#   projects/Workframe/Workframe/  (frozen meta donor - read-only backup)
#
# Usage:
#   .\scripts\workframe\reset-dogfood-docker.ps1 -WhatIf     # preview
#   .\scripts\workframe\reset-dogfood-docker.ps1 -Confirm    # wipe + leave stack down
#   .\scripts\workframe\reset-dogfood-docker.ps1 -Confirm -Up -Prune  # wipe + prune images + fresh up
#
param(
  [switch]$WhatIf,
  [switch]$Confirm,
  [switch]$Up,
  [switch]$SkipBuild,
  [switch]$Prune
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Runtime = Join-Path $Root 'runtime'
$Agents = Join-Path $Runtime 'Agents'
$Files = Join-Path $Runtime 'Files'
$ApiData = Join-Path $Runtime 'workframe-api-data'
$Compose = Join-Path $Root 'infra\compose\workframe'
$LocalHermes = Join-Path $env:LOCALAPPDATA 'hermes'

function Trim-DogfoodFiles([string]$FilesDir) {
  if (-not (Test-Path $FilesDir)) { return }
  Get-ChildItem $FilesDir -Force | Where-Object { $_.Name -ne 'README.md' } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  foreach ($junk in @('User', 'content')) {
    $path = Join-Path $FilesDir $junk
    if (Test-Path $path) { Remove-Item -Recurse -Force $path -ErrorAction SilentlyContinue }
  }
}

function Trim-DogfoodAgentsRoot([string]$AgentsDir) {
  if (-not (Test-Path $AgentsDir)) { return }
  $junk = @('content', 'User', 'pytest_cache', '__pycache__', '.pytest_cache')
  foreach ($name in $junk) {
    $path = Join-Path $AgentsDir $name
    if (Test-Path $path) {
      Remove-Item -Recurse -Force $path -ErrorAction SilentlyContinue
    }
  }
}


$AllowedRoots = @(
  (Resolve-Path $Runtime).Path.ToLowerInvariant()
)

function Assert-DogfoodPath([string]$Path) {
  $resolved = (Resolve-Path $Path -ErrorAction SilentlyContinue)
  if (-not $resolved) { return }
  $norm = $resolved.Path.ToLowerInvariant()
  foreach ($root in $AllowedRoots) {
    if ($norm.StartsWith($root)) { return }
  }
  throw "Refusing to touch path outside runtime/: $Path"
}

function Guard-ForbiddenPaths() {
  $forbidden = @($LocalHermes)
  foreach ($f in $forbidden) {
    if (-not (Test-Path $f)) { continue }
    foreach ($target in @($Agents, $Files, $ApiData)) {
      if (-not (Test-Path $target)) { continue }
      $t = (Resolve-Path $target).Path
      $item = Get-Item $t -Force -ErrorAction SilentlyContinue
      if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        $junctionTarget = (Get-Item $t).Target
        if ($junctionTarget -and $junctionTarget -match 'hermes|workframe\\workframe') {
          throw "Refusing: $t is a junction - run isolate-local-runtime.ps1 -Fresh first"
        }
      }
    }
  }
}

if (-not $WhatIf -and -not $Confirm) {
  Write-Host @'
Dogfood reset requires -Confirm (or -WhatIf to preview).

This deletes ONLY:
  runtime/Agents, runtime/Files, runtime/workframe-api-data

This does NOT delete:
  repository source (services, apps, packages, infra)
  %LOCALAPPDATA%\hermes (host Hermes � off limits)
  
'@
  exit 1
}

Guard-ForbiddenPaths
Assert-DogfoodPath $Agents
Assert-DogfoodPath $Files
Assert-DogfoodPath $ApiData

Write-Host '=== Dogfood reset plan ==='
Write-Host "  DELETE  $Agents"
Write-Host "  DELETE  $Files"
Write-Host "  DELETE  $ApiData\*"
Write-Host "  KEEP    $Root\services, apps, packages"
Write-Host "  KEEP    $LocalHermes"
Write-Host ''

if ($WhatIf) {
  Write-Host 'WhatIf: no changes made.'
  exit 0
}

Write-Host '=== docker compose down ==='
Push-Location $Compose
$composeFiles = @('-f', 'docker-compose.yml', '-f', 'docker-compose.dev-authority.yml')
$downArgs = @('compose') + $composeFiles + @('down', '--remove-orphans')
if ($Prune) { $downArgs += '--rmi', 'local' }
docker @downArgs
if ($Prune) {
  Write-Host '=== docker prune (dangling images + build cache) ==='
  docker image prune -f
  docker builder prune -f
}
Pop-Location

Write-Host '=== wipe runtime ==='
if (Test-Path $Agents) {
  Remove-Item -Recurse -Force $Agents
}
if (Test-Path $Files) {
  Remove-Item -Recurse -Force $Files
}
New-Item -ItemType Directory -Force -Path $Files | Out-Null
$readmeTemplate = Join-Path $Root 'packages\create-workframe\rules\workspace-README.md'
$projectName = if ($env:WORKFRAME_PROJECT) { $env:WORKFRAME_PROJECT } else { 'Workframe' }
if (Test-Path $readmeTemplate) {
  $readme = (Get-Content $readmeTemplate -Raw).Replace('{projectName}', $projectName)
  Set-Content -Path (Join-Path $Files 'README.md') -Value $readme -NoNewline
} else {
  @"
# $projectName

Welcome to Workframe - your team's social AI collaboration space.

Use this file to keep a living record of what this project is, who is on the team, sub-projects, agents, kanban guidelines, and anything else newcomers should know. Your Workframe Agent can help you evolve it over time.
"@ | Set-Content -Path (Join-Path $Files 'README.md')
}
New-Item -ItemType Directory -Force -Path (Join-Path $Agents 'profiles') | Out-Null

if (Test-Path $ApiData) {
  Remove-Item -Recurse -Force (Join-Path $ApiData '*') -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force -Path $ApiData | Out-Null

Write-Host '=== runtime wiped (dogfood only) ==='

if (-not $Up) {
  Write-Host ''
  Write-Host 'Stack is DOWN. To bring up fresh:'
  Write-Host "  .\scripts\workframe\reset-dogfood-docker.ps1 -Confirm -Up"
  exit 0
}

$Seed = Join-Path $Root 'scripts\workframe\seed\profiles\workframe-agent'
Write-Host '=== bootstrap workframe-agent in empty runtime ==='
docker run --rm --entrypoint hermes `
  -v "${Agents}:/opt/data" `
  -v "${Files}:/workspace" `
  nousresearch/hermes-agent:latest `
  profile create workframe-agent --clone --description "Workframe native agent"
if (Test-Path (Join-Path $Seed 'SOUL.md')) {
  Copy-Item (Join-Path $Seed 'SOUL.md') (Join-Path $Agents 'profiles\workframe-agent\SOUL.md') -Force
}
& (Join-Path $PSScriptRoot 'bootstrap-native-profile.ps1') -AgentsRoot $Agents

if (-not $SkipBuild) {
  Write-Host '=== build web (workframe + preset assets) ==='
  Push-Location $Root
  pnpm --filter @workframe/web build
  Pop-Location
}

Write-Host '=== docker compose up ==='
Push-Location $Compose
docker compose -f docker-compose.yml -f docker-compose.dev-authority.yml up -d --build
Pop-Location

Write-Host '=== post-compose trim (Hermes may seed junk on first boot) ==='
Start-Sleep -Seconds 4
Trim-DogfoodFiles $Files
Trim-DogfoodAgentsRoot $Agents

Write-Host ''
Write-Host 'Fresh dogfood ready - test checklist:'
Write-Host '  1. http://127.0.0.1:18644 - sign in (email OTP); DB wipe forces full onboarding'
Write-Host '  2. Phase 1: GitHub OAuth (optional skip) + BYOK vs company pays'
Write-Host '  3. Phase 1/2: workspace keys (company) or personal keys (BYOK)'
Write-Host '  4. Agent DM: workframe-agent only; Files shows README.md only'
Write-Host '  5. Hermes bootstrap: nousresearch/hermes-agent:latest (profile.yaml)'
Write-Host ''
Write-Host 'Local Hermes NOT touched:' $LocalHermes
