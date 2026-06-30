# Stop VPS SSH tunnels (ControlMaster + ssh listeners on slot-2 / landing ports).
$ErrorActionPreference = "SilentlyContinue"
$env:SSH_ASKPASS = "D:\HStudio\hermes_ssh_askpass.cmd"
$env:SSH_ASKPASS_REQUIRE = "force"

$ControlPath = Join-Path $env:USERPROFILE ".ssh\workframe-vps-ctrl"
Remove-Item $ControlPath -Force -ErrorAction SilentlyContinue

$ports = @(28642, 28644, 29119, 29120, 28742, 28744, 29219, 29220)
$pids = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object { $_.LocalPort -in $ports -and $_.OwningProcess -ne 0 } |
  Select-Object -ExpandProperty OwningProcess -Unique

foreach ($procId in $pids) {
  $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
  if ($proc -and $proc.ProcessName -eq 'ssh') {
    Write-Host "Stopping ssh PID $procId (ports: $((Get-NetTCPConnection -OwningProcess $procId -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty LocalPort) -join ','))"
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
  }
}

$stateFile = Join-Path $env:USERPROFILE ".ssh\workframe-vps-tunnel.json"
Remove-Item $stateFile -Force -ErrorAction SilentlyContinue
Write-Host "Tunnel stopped."
