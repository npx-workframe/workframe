$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
& "$Root\scripts\verify-bootstrap.ps1"
if (docker ps -aq -f "name=^workframe-chat$") {
  docker rm -f "workframe-chat"
}
docker run --rm -it --name "workframe-chat" --entrypoint hermes `
  -v "$Root\Agents:/opt/data" `
  -v "$Root\Files:/workspace" `
  nousresearch/hermes-agent:latest -p workframe-agent chat @args
