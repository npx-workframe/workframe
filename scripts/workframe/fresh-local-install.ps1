# DEPRECATED — use reset-dogfood-docker.ps1 (npx create-workframe only).
Write-Warning 'fresh-local-install.ps1 is deprecated. Running reset-dogfood-docker.ps1 -Confirm instead.'
& (Join-Path $PSScriptRoot 'reset-dogfood-docker.ps1') -Confirm @args
