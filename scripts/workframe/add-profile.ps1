param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Profile
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Allowed = @('architect', 'designer', 'dev', 'docs', 'research', 'visionary')
if ($Profile -eq 'workframe-agent') {
  throw "Use bootstrap-native for workframe-agent."
}
if ($Allowed -notcontains $Profile) {
  throw "Unknown profile '$Profile'. Available: $($Allowed -join ', ')"
}
if (-not (Test-Path "$Root\Agents")) {
  throw "Agents/ missing. Run Hermes setup first."
}

$Descriptions = @{
  'architect' = 'Defines system design, technical boundaries, implementation plans, and code-review standards.'
  'designer' = 'Handles UI direction, design docs, visual assets, image prompts, brand direction, and layout feedback.'
  'dev' = 'Builds and modifies project files, scripts, tests, and implementation artifacts.'
  'docs' = 'Maintains AGENTS.md, .hermes.md, docs indexes, source-of-truth maps, and change summaries.'
  'research' = 'Performs technical research, market research, references, competitive analysis, and R&D notes.'
  'visionary' = 'Clarifies product purpose, positioning, strategy, user value, and long-term alignment.'
}
$desc = $Descriptions[$Profile]

$createOut = docker run --rm --name "workframe-add-$Profile" --entrypoint hermes `
  -v "$Root\Agents:/opt/data" `
  -v "$Root\Files:/workspace" `
  nousresearch/hermes-agent:latest profile create $Profile --clone --description "$desc" 2>&1
if ($LASTEXITCODE -ne 0) {
  docker run --rm --name "workframe-add-$Profile-show" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile show $Profile 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) {
    Write-Host "Profile $Profile already exists, continuing."
  } else {
    throw "Failed to create profile $($Profile): $createOut"
  }
}

$seed = Join-Path $Root "scripts\seed\profiles\$Profile\SOUL.md"
$destDir = Join-Path $Root "Agents\profiles\$Profile"
if (Test-Path $seed) {
  New-Item -ItemType Directory -Force -Path $destDir | Out-Null
  Copy-Item $seed (Join-Path $destDir "SOUL.md") -Force
}

@"
description: "$desc"
description_auto: false
soul:
  file: /opt/data/profiles/$Profile/SOUL.md
"@ | Set-Content -Path (Join-Path $destDir "profile.yaml") -Encoding UTF8

Write-Host "Profile $Profile ready."
