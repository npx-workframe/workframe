# Reset dogfood + run trusted_team install E2E (Playwright).
# SMTP: set in generated MyBusiness/.env after wizard, or copy e2e-smtp.local.env.example → e2e-smtp.local.env
param(
  [switch]$SkipReset,
  [string]$ProjectName = 'MyBusiness',
  [string]$InstallRoot = ''
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
if (-not $InstallRoot) {
  $InstallRoot = (Resolve-Path (Join-Path $root '..')).Path
}
$installDir = Join-Path $InstallRoot $ProjectName
$envFile = Join-Path $installDir '.env'
$localSmtp = Join-Path $PSScriptRoot 'e2e-smtp.local.env'

function Read-EnvKey([string]$path, [string]$key) {
  if (-not (Test-Path $path)) { return '' }
  $line = Get-Content $path | Where-Object { $_ -match "^$key=" } | Select-Object -First 1
  if (-not $line) { return '' }
  ($line -split '=', 2)[1].Trim()
}

function Read-SmtpFrom([string]$path) {
  @('SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASS', 'EMAIL_FROM') | ForEach-Object {
    if (-not (Read-EnvKey $path $_)) { return $false }
  }
  return $true
}

$smtpSource = $null
if ((Test-Path $localSmtp) -and (Read-SmtpFrom $localSmtp)) {
  $smtpSource = $localSmtp
} elseif ((Test-Path $envFile) -and (Read-SmtpFrom $envFile)) {
  $smtpSource = $envFile
} else {
  Write-Warning @"
SMTP not configured. Copy:
  scripts/workframe/e2e-smtp.local.env.example → e2e-smtp.local.env
or complete wizard SMTP on $installDir first.
"@
}

if ($smtpSource) {
  $env:WORKFRAME_E2E = '1'
  $env:WORKFRAME_E2E_SMTP_HOST = Read-EnvKey $smtpSource 'SMTP_HOST'
  $env:WORKFRAME_E2E_SMTP_PORT = Read-EnvKey $smtpSource 'SMTP_PORT'
  $env:WORKFRAME_E2E_SMTP_USER = Read-EnvKey $smtpSource 'SMTP_USER'
  $env:WORKFRAME_E2E_SMTP_PASS = Read-EnvKey $smtpSource 'SMTP_PASS'
  $env:WORKFRAME_E2E_SMTP_FROM = Read-EnvKey $smtpSource 'EMAIL_FROM'
  $env:WORKFRAME_E2E_ADMIN_EMAIL = Read-EnvKey $smtpSource 'SMTP_USER'
}

if (-not $SkipReset) {
  & "$PSScriptRoot\reset-dogfood-docker.ps1" -Confirm -ProjectName $ProjectName -InstallRoot $InstallRoot
}

$spec = Join-Path $root 'apps\web\e2e\full-install-trusted.spec.ts'
if (-not (Test-Path $spec)) {
  Write-Warning "Playwright spec missing: $spec — complete wizard manually at http://127.0.0.1:18644/"
  exit 0
}

Push-Location (Join-Path $root 'apps\web')
try {
  npx playwright test e2e/full-install-trusted.spec.ts --project=chromium
} finally {
  Pop-Location
}
