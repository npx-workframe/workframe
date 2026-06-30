# Copy canonical workframe-agent identity from create-workframe package into runtime profile dir.
param(
  [string]$AgentsRoot = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path 'runtime\Agents'),
  [string]$ProfileSlug = 'workframe-agent'
)

$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$Pkg = Join-Path $Root 'packages\create-workframe\profiles\workframe-agent'
$Dest = Join-Path $AgentsRoot "profiles\$ProfileSlug"
$projectName = if ($env:WORKFRAME_PROJECT) { $env:WORKFRAME_PROJECT } else { 'Workframe' }
$nativeAgentName = "$projectName Agent"

if (-not (Test-Path $Dest)) {
  throw "Profile dir missing: $Dest (run hermes profile create first)"
}

function Render-SoulPlaceholders([string]$Text) {
  return $Text.Replace('{projectName}', $projectName).
    Replace('{nativeProfileSlug}', $ProfileSlug).
    Replace('{nativeAgentName}', $nativeAgentName)
}

foreach ($file in @('SOUL.md', 'AGENTS.md', 'SETUP.md')) {
  $src = Join-Path $Pkg $file
  if (Test-Path $src) {
    $content = Get-Content $src -Raw -Encoding UTF8
    if ($file -eq 'SOUL.md') {
      $content = Render-SoulPlaceholders $content
    }
    Set-Content -Path (Join-Path $Dest $file) -Value $content -Encoding utf8 -NoNewline
  }
}

$skillsSrc = Join-Path $Pkg 'skills'
$skillsDest = Join-Path $Dest 'skills'
if (Test-Path $skillsSrc) {
  New-Item -ItemType Directory -Force -Path $skillsDest | Out-Null
  Copy-Item -Path (Join-Path $skillsSrc '*') -Destination $skillsDest -Recurse -Force
}

Write-Host "Bootstrapped $ProfileSlug identity from create-workframe package -> $Dest"
