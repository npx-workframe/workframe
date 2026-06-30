$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

New-Item -ItemType Directory -Force -Path Agents, Files | Out-Null

Write-Host 'Pulling Hermes image...'
docker pull nousresearch/hermes-agent:latest

Write-Host @'

Workframe Phase B — use ONE of these:

  FULL (recommended — credentials → native agent → gateway):
    .scriptsstart-install.ps1

  Open full installer in new window (TTY-friendly):
    .scriptslaunch-install.ps1

  Already ran Hermes setup? Finish boot:
    .scriptsinstall.ps1

  Credentials / dashboard only:
    .scriptsopen-setup.ps1

Phase C — chat with Workframe Agent:
  .scriptschat.ps1

WARNING: docker run ... hermes-agent:latest WITHOUT -p workframe-agent
         starts generic default Hermes (OWL) — not Workframe Agent.
'@
