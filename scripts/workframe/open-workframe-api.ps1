$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$ApiPort = '18644'
$envFile = Join-Path $Root '.env'
if (Test-Path $envFile) {
  $line = Get-Content $envFile | Where-Object { $_ -match '^WORKFRAME_UI_PORT=' } | Select-Object -Last 1
  if ($line) { $ApiPort = ($line -split '=', 2)[1].Trim() }
}

$url = "http://127.0.0.1:$ApiPort/"
Write-Host "Opening Workframe auth/UI: $url"
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
