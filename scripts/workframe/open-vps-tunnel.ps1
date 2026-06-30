# VPS Workframe slot 2 SSH tunnel.
# Canonical local ports = remote (28644, ...). If blocked, uses +100 landing ports (28744 UI).
$ErrorActionPreference = "Stop"
$env:SSH_ASKPASS = "D:\HStudio\hermes_ssh_askpass.cmd"
$env:SSH_ASKPASS_REQUIRE = "force"

$remote = @{ gateway = 28642; ui = 28644; dashboard = 29119; api = 29120 }
$stateFile = Join-Path $env:USERPROFILE ".ssh\workframe-vps-tunnel.json"

function Test-PortFree([int]$port) {
  return -not (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Start-TunnelProcess([hashtable]$local, [hashtable]$remote) {
  $forwards = @()
  foreach ($key in @("gateway", "ui", "dashboard", "api")) {
    $forwards += "-L", "127.0.0.1:$($local[$key]):127.0.0.1:$($remote[$key])"
  }
  $sshArgs = @(
    "-N",
    "-o", "BatchMode=yes",
    "-o", "ExitOnForwardFailure=yes",
    "-o", "ServerAliveInterval=30",
    "-o", "ServerAliveCountMax=3"
  ) + $forwards + @("hetzner-hermes")
  Start-Process -FilePath "ssh" -ArgumentList $sshArgs -WindowStyle Hidden
}

& "$PSScriptRoot\stop-vps-tunnel.ps1"

$local = @{ gateway = $remote.gateway; ui = $remote.ui; dashboard = $remote.dashboard; api = $remote.api }
$mode = "canonical"
foreach ($p in $local.Values) {
  if (-not (Test-PortFree $p)) { $mode = "landing"; break }
}
if ($mode -eq "landing") {
  Write-Host "Canonical 28xxx busy - using +100 landing ports (28744 UI)."
  $local = @{ gateway = 28742; ui = 28744; dashboard = 29219; api = 29220 }
}

Start-TunnelProcess $local $remote

$deadline = (Get-Date).AddSeconds(20)
$health = $null
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Milliseconds 800
  try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:$($local.api)/api/health" -UseBasicParsing -TimeoutSec 5
    if ($health.StatusCode -eq 200) { break }
  } catch { }
}
if (-not $health) { throw "Tunnel did not become healthy on port $($local.api)" }

@{
  mode = $mode
  local = $local
  remote = $remote
  ui_url = "http://127.0.0.1:$($local.ui)/"
  api_url = "http://127.0.0.1:$($local.api)/api/health"
} | ConvertTo-Json | Set-Content $stateFile -Encoding UTF8

Write-Host "Tunnel up ($mode). UI: http://127.0.0.1:$($local.ui)/"
Write-Host $health.Content
