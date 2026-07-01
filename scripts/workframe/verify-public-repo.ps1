# Fail if tracked public repo contains private paths or operator-defined patterns.
# Operator denylist: scripts/workframe/verify-public-patterns.local.json (gitignored).
$ErrorActionPreference = 'Stop'
$env:VERIFY_PUBLIC_STRICT = '1'
node (Join-Path $PSScriptRoot 'verify-public-repo.mjs')
exit $LASTEXITCODE
