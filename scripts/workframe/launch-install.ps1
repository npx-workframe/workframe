$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Root 'scripts\start-install.ps1'
Start-Process powershell -ArgumentList @('-NoExit', '-File', $Script)
Write-Host 'Opened Phase B installer in a new window.'
Write-Host 'Complete Hermes setup there - browser chat opens automatically at /chat when done.'
