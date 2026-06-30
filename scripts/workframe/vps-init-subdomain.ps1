# VPS bootstrap — public_multi_user (PowerShell wrapper).
param(
  [Parameter(Mandatory = $true)][string]$Domain,
  [Parameter(Mandatory = $true)][string]$AdminEmail
)

$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$sh = Join-Path $PSScriptRoot "vps-init-subdomain.sh"
if (-not (Test-Path $sh)) { throw "Missing $sh" }
bash $sh $Domain $AdminEmail
