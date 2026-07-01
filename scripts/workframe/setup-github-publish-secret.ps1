# Print VERIFY_PUBLIC_PATTERNS_JSON for GitHub Actions (paste into repo secret).
# Usage: .\scripts\workframe\setup-github-publish-secret.ps1
$ErrorActionPreference = 'Stop'
$path = Join-Path $PSScriptRoot 'verify-public-patterns.local.json'
if (-not (Test-Path -LiteralPath $path)) {
  throw @'
missing verify-public-patterns.local.json
  copy verify-public-patterns.example.json → verify-public-patterns.local.json
'@
}
$json = Get-Content -LiteralPath $path -Raw
Write-Host 'GitHub → Settings → Secrets → Actions → New secret'
Write-Host '  Name:  VERIFY_PUBLIC_PATTERNS_JSON'
Write-Host '  Value: (copy everything below this line)'
Write-Host '---'
Write-Host $json.TrimEnd()
Write-Host '---'
if (Get-Command gh -ErrorAction SilentlyContinue) {
  Write-Host ''
  Write-Host 'Or run (from repo root):'
  Write-Host "  gh secret set VERIFY_PUBLIC_PATTERNS_JSON < `"$path`""
}
