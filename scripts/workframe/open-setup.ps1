$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$DashPort = '18269'
$envFile = Join-Path $Root '.env'
if (Test-Path $envFile) {
  $line = Get-Content $envFile | Where-Object { $_ -match '^WORKFRAME_DASHBOARD_PORT=' } | Select-Object -Last 1
  if ($line) {
    $DashPort = ($line -split '=', 2)[1].Trim()
  }
}

Write-Host 'Workframe secure setup - credentials never belong in chat.'
Write-Host ''
Write-Host 'Full Phase B (recommended): .\scripts\start-install.ps1'
Write-Host ''
Write-Host 'Hermes setup only (interactive, writes to Agents/):'
Write-Host "  docker run --rm -it --name workframe-setup --entrypoint hermes `"
Write-Host '    -v "$PWD\Agents:/opt/data" `'
Write-Host '    -v "$PWD\Files:/workspace" `'
Write-Host '    nousresearch/hermes-agent:latest setup'
Write-Host ''
$url = "http://127.0.0.1:$DashPort"
Write-Host "Dashboard (ops UI): $url"
try {
  Start-Process $url | Out-Null
} catch {
  Write-Host 'Open the dashboard URL manually in your browser.'
}
