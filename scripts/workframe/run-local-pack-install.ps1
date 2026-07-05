# DEPRECATED — use sign-off-install.ps1 (install-gate + npx create-workframe reset).
Write-Warning 'run-local-pack-install.ps1 is deprecated. Running sign-off-install.ps1 instead.'
param(
  [string]$ProjectName = 'MyBusiness',
  [string]$InstallRoot = '',
  [switch]$SkipGate
)
& (Join-Path $PSScriptRoot 'sign-off-install.ps1') -ProjectName $ProjectName -InstallRoot $InstallRoot -SkipGate:$SkipGate
