# Publish Workframe npm packages. Complete browser OTP when prompted.
# Usage: .\scripts\workframe\publish-npm.ps1
param([switch]$SkipWorkframe)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

Write-Host '=== verify public repo ==='
$localPatterns = Join-Path $PSScriptRoot 'verify-public-patterns.local.json'
if (-not (Test-Path -LiteralPath $localPatterns)) {
  throw @'
missing scripts/workframe/verify-public-patterns.local.json
  copy verify-public-patterns.example.json → verify-public-patterns.local.json
  and fill in your operator denylist (gitignored — never commit).
'@
}
& (Join-Path $PSScriptRoot 'verify-public-repo.ps1')
if ($LASTEXITCODE -ne 0) { throw 'public repo verify failed — fix hits before publish' }

Write-Host '=== release local gates ==='
node (Join-Path $Root 'scripts\workframe\verify-release-gates.mjs')
if ($LASTEXITCODE -ne 0) { throw 'release gates blocked — complete sign-off before publish' }

Write-Host '=== npm whoami ==='
npm whoami
if ($LASTEXITCODE -ne 0) { throw 'npm login required: npm login' }

# ponytail: WF-038 — only create-workframe ships; stub CLIs removed.
$pkgDir = Join-Path $Root 'packages\create-workframe'

Write-Host ""
Write-Host '=== publishing create-workframe ===' -ForegroundColor Cyan
Push-Location $pkgDir
try {
  npm publish --access public
  if ($LASTEXITCODE -ne 0) { throw "publish failed for create-workframe ($LASTEXITCODE)" }
  Write-Host 'OK: create-workframe' -ForegroundColor Green
} finally {
  Pop-Location
}

Write-Host ""
Write-Host '=== verify (registry may lag ~30s) ===' -ForegroundColor Cyan
for ($i = 1; $i -le 12; $i++) {
  $v = npm view create-workframe version 2>$null
  if ($LASTEXITCODE -eq 0 -and $v) { Write-Host "create-workframe@$v" -ForegroundColor Green; break }
  if ($i -eq 12) { throw 'npm view failed for create-workframe' }
  Start-Sleep -Seconds 5
}
Write-Host 'OK: publish complete' -ForegroundColor Green
