$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path "$Root\Agents")) {
  throw "Agents/ missing. Run Hermes setup first."
}

Write-Host "Creating profile: workframe-agent"
$profilesRoot = Join-Path $Root "Agents\profiles"
$profileDir = Join-Path $profilesRoot "workframe-agent"
$profileConfig = Join-Path $profileDir "config.yaml"
New-Item -ItemType Directory -Force -Path $profilesRoot | Out-Null

docker run --rm --name "workframe-bootstrap-native-show-precheck" --entrypoint hermes `
  -v "$Root\Agents:/opt/data" `
  -v "$Root\Files:/workspace" `
  nousresearch/hermes-agent:latest profile show workframe-agent 2>$null | Out-Null
$profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
if ($profileReady) {
  Write-Host "Profile workframe-agent already exists, continuing."
} else {
  docker run --rm --name "workframe-bootstrap-native-clean" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile delete -y workframe-agent 2>$null | Out-Null
  if (Test-Path $profileDir) {
    Remove-Item -Recurse -Force $profileDir
  }
  $createOut = docker run --rm --name "workframe-bootstrap-native" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile create workframe-agent --clone --description "Workframe Agent: Workframe Manager, orchestrator, and Workframe admin." 2>&1
  if ($LASTEXITCODE -ne 0) {
    docker run --rm --name "workframe-bootstrap-native-show" --entrypoint hermes `
      -v "$Root\Agents:/opt/data" `
      -v "$Root\Files:/workspace" `
      nousresearch/hermes-agent:latest profile show workframe-agent 2>$null | Out-Null
    $profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
    if ($profileReady) {
      Write-Host "Profile workframe-agent already exists, continuing."
    } else {
      Write-Host "Retrying profile create after cleaning incomplete registration: workframe-agent"
      docker run --rm --name "workframe-bootstrap-native-clean-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile delete -y workframe-agent 2>$null | Out-Null
      if (Test-Path $profileDir) {
        Remove-Item -Recurse -Force $profileDir
      }
      $createOut = docker run --rm --name "workframe-bootstrap-native-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile create workframe-agent --clone --description "Workframe Agent: Workframe Manager, orchestrator, and Workframe admin." 2>&1
      if ($LASTEXITCODE -ne 0) {
        throw "Failed to create profile workframe-agent: $createOut"
      }
    }
  }
}

$seed = Join-Path $Root "scripts\seed\profiles\workframe-agent\SOUL.md"
$destDir = Join-Path $Root "Agents\profiles\workframe-agent"
if (Test-Path $seed) {
  New-Item -ItemType Directory -Force -Path $destDir | Out-Null
  Copy-Item $seed (Join-Path $destDir "SOUL.md") -Force
  Copy-Item $seed (Join-Path $Root "Agents\SOUL.md") -Force
}
$setupSeed = Join-Path $Root "scripts\seed\profiles\workframe-agent\SETUP.md"
if (Test-Path $setupSeed) {
  Copy-Item $setupSeed (Join-Path $destDir "SETUP.md") -Force
}

@"
description: "Native Workframe agent: host, concierge, project manager, orchestrator, and Workframe admin."
description_auto: false
soul:
  file: /opt/data/profiles/workframe-agent/SOUL.md
"@ | Set-Content -Path (Join-Path $destDir "profile.yaml") -Encoding UTF8

$routesDir = Join-Path $Root "Agents\workframe"
New-Item -ItemType Directory -Force -Path $routesDir | Out-Null
@'
{
  "version": 1,
  "default_profile": "workframe-agent",
  "routes": [
    {
      "id": "workframe-agent",
      "surface": "ui",
      "channel_id": "ui://agent/workframe-agent",
      "profile": "workframe-agent",
      "display_name": "Workframe Agent",
      "role": "Workframe Agent: Workframe Manager, orchestrator, and Workframe admin.",
      "mode": "lane"
    }
  ]
}
'@ | Set-Content -Path (Join-Path $routesDir "routes.json") -Encoding utf8

$cfg = Join-Path $destDir "config.yaml"
if (Test-Path $cfg) {
  $content = Get-Content $cfg -Raw
  $content = $content -replace '(?m)^  cwd: .*', '  cwd: /workspace'
  Set-Content -Path $cfg -Value $content -NoNewline
}

Write-Host "Setting default profile to workframe-agent..."
docker run --rm --name "workframe-bootstrap-use" --entrypoint hermes `
  -v "$Root\Agents:/opt/data" `
  -v "$Root\Files:/workspace" `
  nousresearch/hermes-agent:latest profile use workframe-agent

Write-Host "Native bootstrap complete (workframe-agent). Create agents: node scripts/agent-lifecycle.mjs create --slug <name> --spawn"
docker run --rm --name "workframe-bootstrap-list" --entrypoint hermes `
  -v "$Root\Agents:/opt/data" `
  -v "$Root\Files:/workspace" `
  nousresearch/hermes-agent:latest profile list
