# Publish Workframe npm packages. Complete browser OTP when prompted.
# Usage: .\scripts\workframe\publish-npm.ps1
param([switch]$SkipWorkframe)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

Write-Host '=== verify public repo ==='
& (Join-Path $PSScriptRoot 'verify-public-repo.ps1')

Write-Host '=== npm whoami ==='
npm whoami
if ($LASTEXITCODE -ne 0) { throw 'npm login required: npm login' }

$steps = @()
if (-not $SkipWorkframe) {
  $steps += @{ Name = 'workframe'; Dir = Join-Path $Root 'packages\workframe' }
}
$steps += @(
  @{ Name = 'create-workframe'; Dir = Join-Path $Root 'packages\create-workframe' }
  @{ Name = '@workframe/workframe'; Dir = Join-Path $Root 'packages\workframe-scoped' }
)

foreach ($step in $steps) {
  Write-Host ""
  Write-Host "=== publishing $($step.Name) ===" -ForegroundColor Cyan
  Push-Location $step.Dir
  try {
    npm publish --access public
    if ($LASTEXITCODE -ne 0) { throw "publish failed for $($step.Name) ($LASTEXITCODE)" }
    Write-Host "OK: $($step.Name)" -ForegroundColor Green
  } finally {
    Pop-Location
  }
}

Write-Host ""
Write-Host '=== verify (registry may lag ~30s) ===' -ForegroundColor Cyan
function Wait-View($pkg) {
  for ($i = 1; $i -le 12; $i++) {
    $v = npm view $pkg version 2>$null
    if ($LASTEXITCODE -eq 0 -and $v) { Write-Host "$pkg@$v" -ForegroundColor Green; return }
    if ($i -lt 12) { Start-Sleep -Seconds 5 }
  }
  throw "npm view failed for $pkg"
}
if (-not $SkipWorkframe) { Wait-View 'workframe' }
Wait-View 'create-workframe'
Wait-View '@workframe/workframe'
Write-Host 'OK: publish complete' -ForegroundColor Green
