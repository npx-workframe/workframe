$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$MissionPort = ''
$envFile = Join-Path $Root '.env'
if (Test-Path $envFile) {
  $line = Get-Content $envFile | Where-Object { $_ -match '^WORKFRAME_MISSION_PORT=' } | Select-Object -Last 1
  if ($line) { $MissionPort = ($line -split '=', 2)[1].Trim() }
}

if (-not $MissionPort) {
  Write-Host 'Mission control is deprecated and not enabled in the default Workframe stack.'
  Write-Host 'Use Workframe UI or Workframe API instead.'
  exit 0
}

$url = "http://127.0.0.1:$MissionPort/"
Write-Host "Opening Workframe mission control: $url"
$deadline = (Get-Date).AddSeconds(45)
while ((Get-Date) -lt $deadline) {
  try {
    $null = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
    break
  } catch {
    Start-Sleep -Seconds 2
  }
}
try {
  Start-Process $url | Out-Null
} catch {
  Write-Host "Open manually: $url"
}
