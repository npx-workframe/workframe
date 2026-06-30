$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$UiRoot = Join-Path $Root 'apps\web'

Write-Host 'Building Workframe UI (@workframe/web)...'
Push-Location $Root
pnpm --filter @workframe/web build
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { exit $code }

Write-Host 'Done. Dist:' (Join-Path $UiRoot 'dist')
Write-Host 'Dogfood nginx mounts apps/web/dist (or WORKFRAME_UI_STATIC_DIR in compose .env).'
