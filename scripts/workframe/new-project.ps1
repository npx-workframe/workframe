# Meta repo: bundle UI + scaffold + auto-launch Phase B installer.
# Usage: .\scripts\new-project.ps1 BrandAuthority --out D:\Workframe --force
$ErrorActionPreference = 'Stop'
$MetaRoot = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $MetaRoot 'packages\create-workframe\scripts\new-project.mjs'
if (-not (Test-Path $Script)) {
  throw "Missing $Script — run from the Workframe meta repo."
}
node $Script @args
exit $LASTEXITCODE
