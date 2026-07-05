# Release sign-off: build/sync/pack from source, then dogfood reset (npx create-workframe only).
# Usage: .\scripts\workframe\sign-off-install.ps1 [-SkipGate]
param(
  [string]$ProjectName = 'MyBusiness',
  [string]$InstallRoot = '',
  [switch]$SkipGate
)

$ErrorActionPreference = 'Stop'
if (-not $SkipGate) {
  & (Join-Path $PSScriptRoot 'install-gate.ps1') -Quick
}
& (Join-Path $PSScriptRoot 'reset-dogfood-docker.ps1') -Confirm -ProjectName $ProjectName -InstallRoot $InstallRoot
