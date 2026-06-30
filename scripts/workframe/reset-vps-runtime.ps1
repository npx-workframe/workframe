# Wipe VPS runtime + fresh bootstrap + vps-deploy. Preserves .env. Never touches host Hermes.
param(
  [Parameter(Mandatory = $true)] [string]$VpsHost,
  [switch]$DeploySourceFirst
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$remote = $VpsHost

if ($DeploySourceFirst) {
  & "$PSScriptRoot\vps-pull-deploy.ps1" -VpsHost $remote -Source working-tree
}

Write-Host "=== reset VPS runtime on $remote ==="
scp -o BatchMode=yes "$PSScriptRoot\reset-vps-runtime.sh" "${remote}:/tmp/reset-vps-runtime.sh"
ssh -o BatchMode=yes $remote "sed -i 's/\r$//' /tmp/reset-vps-runtime.sh; bash /tmp/reset-vps-runtime.sh"
