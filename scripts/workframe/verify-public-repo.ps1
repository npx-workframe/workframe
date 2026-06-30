# Fail if tracked public repo contains private/operator patterns.
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$patterns = @(
  'alanborger', 'alan@click', 'click\.blue',
  'd:\\ab', 'd:/ab', 'D:\\ab', 'D:/ab',
  'ProjectX', 'projectx', 'hackathon',
  'architectonic/workframe', '95\.216\.136',
  'workframe\.io'
)
$forbiddenPaths = @(
  'services/workframe-api/tests', 'services/workframe-supervisor/tests',
  'apps/web/e2e', 'packages/contracts', 'packages/workframe-integrations', 'docs/integrations'
)
foreach ($f in $forbiddenPaths) {
  if (git -C $Root ls-files -- $f 2>$null) {
    Write-Host "TRACKED FORBIDDEN PATH: $f" -ForegroundColor Red; exit 1
  }
}
$hits = @()
$files = git -C $Root ls-files
foreach ($rel in $files) {
  if ($rel -eq 'scripts/workframe/verify-public-repo.ps1') { continue }
  if ($rel -match '(^|/)(tests|e2e)(/|$)|\.test\.(ts|js)$|\.spec\.(ts|js)$') {
    $hits += "forbidden path: $rel"; continue
  }
  $full = Join-Path $Root $rel
  if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { continue }
  $text = Get-Content -LiteralPath $full -Raw -ErrorAction SilentlyContinue
  if (-not $text) { continue }
  foreach ($p in $patterns) {
    if ($text -match $p) { $hits += "$rel :: $p"; break }
  }
}
if ($hits.Count) {
  Write-Host 'PUBLIC REPO VERIFY FAILED:' -ForegroundColor Red
  $hits | Select-Object -First 50 | ForEach-Object { Write-Host "  $_" }
  exit 1
}
Write-Host 'OK: public repo verify passed' -ForegroundColor Green
