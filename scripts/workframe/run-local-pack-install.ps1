# Clean local install from create-workframe npm pack (product sign-off path).
# NOT canonical dogfood compose — generated install only.
#
# Usage:
#   .\scripts\workframe\run-local-pack-install.ps1
#   .\scripts\workframe\run-local-pack-install.ps1 -SkipGate -Slot 4
param(
  [string]$ProjectName = 'PackTest',
  [string]$OutRoot = '',
  [int]$Slot = 4,
  [string]$PackPath = '',
  [switch]$SkipGate,
  [switch]$CopySecretsFromDogfood
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $OutRoot) { $OutRoot = Join-Path $Root 'runtime\pack-install' }
$GateDir = Join-Path $Root '.install-gate'
$InstallDir = Join-Path $OutRoot $ProjectName
$DogfoodEnv = Join-Path $Root 'infra\compose\workframe\.env'

if (-not $SkipGate) {
  Write-Host '=== install gate (source -> pack) ==='
  & (Join-Path $PSScriptRoot 'install-gate.ps1') -Quick
}

if (-not $PackPath) {
  $pack = Get-ChildItem $GateDir -Filter 'create-workframe-*.tgz' |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if (-not $pack) { throw "no pack in $GateDir; run install-gate first" }
  $PackPath = $pack.FullName
}
if (-not (Test-Path $PackPath)) { throw "pack not found: $PackPath" }

Write-Host "=== pack: $PackPath ==="
Write-Host "=== target: $InstallDir (slot $Slot) ==="

if (Test-Path (Join-Path $InstallDir 'docker-compose.yml')) {
  Write-Host '=== docker compose down (prior pack install) ==='
  Push-Location $InstallDir
  $prevEap = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  docker compose down --remove-orphans 2>&1 | Out-Null
  $ErrorActionPreference = $prevEap
  Pop-Location
}
if (Test-Path $InstallDir) {
  Remove-Item -Recurse -Force $InstallDir
  Write-Host "=== removed $InstallDir ==="
}

$Tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("wf-pack-" + [guid]::NewGuid().ToString('n'))
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
try {
  tar -xzf $PackPath -C $Tmp
  $Pkg = Join-Path $Tmp 'package'
  if (-not (Test-Path (Join-Path $Pkg 'bin\create-workframe.js'))) {
    throw 'pack missing bin/create-workframe.js'
  }

  Write-Host '=== create-workframe (from pack) ==='
  Push-Location $Pkg
  node bin/create-workframe.js $ProjectName `
    --out $OutRoot `
    --slot $Slot `
    --deploy docker `
    --ci `
    --no-launch `
    --run-docker-pull `
    --allow-install-actions
  if ($LASTEXITCODE -ne 0) { throw "create-workframe failed ($LASTEXITCODE)" }
  Pop-Location
}
finally {
  Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
}

if (-not (Test-Path $InstallDir)) { throw "scaffold missing: $InstallDir" }

# ponytail: supervisor gateway restart needs host paths in .env (docker.sock bind resolution).
$installEnv = Join-Path $InstallDir '.env'
$rootEsc = $InstallDir.Replace('\', '/')
$envLines = Get-Content $installEnv
$map = @{}
foreach ($line in $envLines) {
  if ($line -match '^([^#=]+)=(.*)$') { $map[$Matches[1]] = $Matches[2] }
}
$map['WORKFRAME_HOST_COMPOSE_DIR'] = $rootEsc
$map['WORKFRAME_HOST_PROJECT_ROOT'] = $rootEsc
($map.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Key)=$($_.Value)" }) | Set-Content $installEnv -Encoding utf8

New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir 'Agents\profiles') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir 'Files') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir 'workframe-api\data') | Out-Null

if ($CopySecretsFromDogfood -and (Test-Path $DogfoodEnv)) {
  Write-Host '=== merge SMTP/ZK secrets from dogfood .env (OTP only; not product code) ==='
  $installEnv = Join-Path $InstallDir '.env'
  $carry = @(
    'WORKFRAME_SUPERVISOR_TOKEN', 'WORKFRAME_API_TOKEN', 'WORKFRAME_PROXY_TOKEN',
    'WORKFRAME_VAULT_KEK', 'ZK_AUTH_HMAC_KEY', 'ZK_AUTH_ENCRYPTION_KEY',
    'ZK_AUTH_SESSION_SECRET', 'SMTP_HOST', 'SMTP_PORT', 'SMTP_USER',
    'SMTP_PASS', 'EMAIL_FROM', 'WORKFRAME_PROJECT'
  )
  $dog = Get-Content $DogfoodEnv -Raw
  $lines = Get-Content $installEnv
  $map = @{}
  foreach ($line in $lines) {
    if ($line -match '^([^#=]+)=(.*)$') { $map[$Matches[1]] = $Matches[2] }
  }
  foreach ($key in $carry) {
    if ($dog -match "(?m)^$([regex]::Escape($key))=(.*)$") {
      $val = $Matches[1].Trim()
      if ($val) { $map[$key] = $val }
    }
  }
  $rootEsc = $InstallDir.Replace('\', '/')
  $map['WORKFRAME_HOST_COMPOSE_DIR'] = $rootEsc
  $map['WORKFRAME_HOST_PROJECT_ROOT'] = $rootEsc
  ($map.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) | Set-Content $installEnv -Encoding utf8
}

Write-Host '=== bootstrap-native.ps1 ==='
Push-Location $InstallDir
& (Join-Path $InstallDir 'scripts\bootstrap-native.ps1')
if ($LASTEXITCODE -ne 0) { throw "bootstrap-native failed ($LASTEXITCODE)" }

Write-Host '=== docker compose up --build (pack API image) ==='
$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
docker compose up -d --build 2>&1 | Out-Null
$composeExit = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($composeExit -ne 0) { throw "docker compose up failed ($composeExit)" }

$uiPort = (Select-String -Path '.env' -Pattern '^WORKFRAME_UI_PORT=' | Select-Object -Last 1).Line.Split('=', 2)[1].Trim()
$apiPort = (Select-String -Path '.env' -Pattern '^WORKFRAME_API_PORT=' | Select-Object -Last 1).Line.Split('=', 2)[1].Trim()
if (-not $uiPort) { $uiPort = '48644' }
if (-not $apiPort) { $apiPort = '49120' }

Write-Host '=== wait for API health ==='
$health = $null
for ($i = 0; $i -lt 30; $i++) {
  try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$apiPort/api/health" -TimeoutSec 5
    if ($health.ok) { break }
  } catch { Start-Sleep -Seconds 2 }
}
if (-not $health -or -not $health.ok) { throw 'API health unreachable after pack install' }

Write-Host ($health | ConvertTo-Json -Compress)

$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$apiContainer = (docker compose ps --format json 2>$null | Where-Object { $_ -match '^\{' } | ConvertFrom-Json | Where-Object { $_.Service -eq 'workframe-api' }).Name
$ErrorActionPreference = $prevEap
if (-not $apiContainer) { throw 'workframe-api container not found' }

$nativeProfile = (Select-String -Path '.env' -Pattern '^WORKFRAME_NATIVE_PROFILE=' | Select-Object -Last 1).Line.Split('=', 2)[1].Trim()
if (-not $nativeProfile) {
  $manifest = Get-Content 'workframe-manifest.json' -Raw | ConvertFrom-Json
  $nativeProfile = $manifest.native_agent.profile_slug
}
if (-not $nativeProfile) { throw 'could not resolve native profile slug from .env or manifest' }

Write-Host "=== pack image: PyYAML + primary api_server ($nativeProfile) ==="
docker exec $apiContainer python3 -c "import yaml; print('yaml', yaml.__version__)"
$ensureOk = $false
for ($i = 0; $i -lt 6; $i++) {
  if ($i -gt 0) { Start-Sleep -Seconds 10 }
  docker exec $apiContainer python3 -c @"
import server
prof = '$nativeProfile'
ok, out, port = server._configure_profile_api(prof)
print('configure', ok, out, port)
out = server.ensure_profile_api(prof)
print('ensure', out)
print('healthy', server._profile_api_healthy(prof))
"@
  if ($LASTEXITCODE -eq 0) { $ensureOk = $true; break }
  Write-Host "ensure_profile_api retry $($i + 1)/6..."
}
if (-not $ensureOk) { throw 'pack API profile repair check failed' }

Pop-Location

Write-Host ''
Write-Host 'OK: clean pack install'
Write-Host "  dir  $InstallDir"
Write-Host "  UI   http://127.0.0.1:$uiPort/"
Write-Host "  API  http://127.0.0.1:$apiPort/api/health"
Write-Host '  Next: human wizard -> BYOK -> DM chat -> pong'
