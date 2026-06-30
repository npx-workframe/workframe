# Reset dogfood + run full trusted_team install E2E (SMTP from compose .env).
param(
  [switch]$SkipReset
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$envFile = Join-Path $root "infra\compose\workframe\.env"

function Read-EnvKey([string]$key) {
  $line = Get-Content $envFile | Where-Object { $_ -match "^$key=" } | Select-Object -First 1
  if (-not $line) { return "" }
  ($line -split "=", 2)[1].Trim()
}

$env:WORKFRAME_E2E = "1"
$env:WORKFRAME_E2E_SMTP_HOST = Read-EnvKey "SMTP_HOST"
$env:WORKFRAME_E2E_SMTP_PORT = Read-EnvKey "SMTP_PORT"
$env:WORKFRAME_E2E_SMTP_USER = Read-EnvKey "SMTP_USER"
$env:WORKFRAME_E2E_SMTP_PASS = Read-EnvKey "SMTP_PASS"
$env:WORKFRAME_E2E_SMTP_FROM = Read-EnvKey "EMAIL_FROM"
$env:WORKFRAME_E2E_ADMIN_EMAIL = Read-EnvKey "SMTP_USER"

if (-not $SkipReset) {
  & "$PSScriptRoot\reset-dogfood-docker.ps1" -Confirm -Up
}

Push-Location (Join-Path $root "apps\web")
try {
  npx playwright test e2e/full-install-trusted.spec.ts --project=chromium
} finally {
  Pop-Location
}
