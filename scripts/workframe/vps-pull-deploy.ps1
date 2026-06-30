# Push repo to VPS via tarball when the server cannot git clone.
param(
  [Parameter(Mandatory = $true)]
  [string]$VpsHost,
  [string]$PublicHost = "",
  [ValidateSet("working-tree", "main")]
  [string]$Source = "working-tree"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$tar = Join-Path $env:TEMP "workframe-deploy.tar"
$remote = $VpsHost

Push-Location $root
try {
  if ($Source -eq "main") {
    git archive -o $tar main
  } else {
    $tar = & "$PSScriptRoot\pack-project-tarball.ps1" -OutPath $tar -Root $root
  }
  scp -o BatchMode=yes $tar "${remote}:/tmp/workframe-deploy.tar"
  scp -o BatchMode=yes "$PSScriptRoot\vps-pull-deploy.sh" "${remote}:/tmp/vps-pull-deploy.sh"
  $hostArg = ""
  if ($PublicHost.Trim()) { $hostArg = $PublicHost.Trim() }
  ssh -o BatchMode=yes $remote "sed -i 's/\r$//' /tmp/vps-pull-deploy.sh; bash /tmp/vps-pull-deploy.sh /tmp/workframe-deploy.tar '$hostArg'"
} finally {
  Pop-Location
}
