$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$UiPort = '18644'
$envFile = Join-Path $Root '.env'
if (Test-Path $envFile) {
  $line = Get-Content $envFile | Where-Object { $_ -match '^WORKFRAME_UI_PORT=' } | Select-Object -Last 1
  if ($line) { $UiPort = ($line -split '=', 2)[1].Trim() }
}

$dist = Join-Path $Root 'packages\workframe-ui\dist\index.html'
if (-not (Test-Path $dist)) {
  Write-Host 'No build found — running build-workframe-ui.ps1 first...'
  & (Join-Path $Root 'scripts\build-workframe-ui.ps1')
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host 'Starting workframe UI container (if needed)...'
docker compose up -d workframe
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$url = "http://127.0.0.1:$UiPort/"
Write-Host "Opening Workframe UI: $url"
$deadline = (Get-Date).AddSeconds(30)
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
