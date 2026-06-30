$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$soul = Join-Path $Root 'Agents\profiles\workframe-agent\SOUL.md'
if (-not (Test-Path $soul)) {
  throw @"
Workframe not bootstrapped.
Run: .\scripts\bootstrap-native.ps1
Full pack fallback: .\scripts\bootstrap-profiles.ps1
Bare Hermes default profile is NOT a Workframe install.
"@
}
$homeSoul = Join-Path $Root 'Agents\SOUL.md'
if (-not (Test-Path $homeSoul) -or -not (Select-String -Path $homeSoul -Pattern 'Workframe concierge' -Quiet)) {
  throw @"
Agents/SOUL.md missing Workframe native identity.
Re-run: .\scripts\bootstrap-native.ps1
"@
}
$cfgYaml = Join-Path $Root "Agents\profiles\workframe-agent\profile.yaml"
$cfg = Join-Path $Root "Agents\profiles\workframe-agent\config.yaml"
$configPath = if (Test-Path $cfgYaml) { $cfgYaml } elseif (Test-Path $cfg) { $cfg } else { $null }
if ($configPath -and (Select-String -Path $configPath -Pattern '^  cwd: \.$' -Quiet)) {
  throw @"
Profile terminal.cwd must be /workspace (Files/), not .
Re-run: .\scripts\bootstrap-native.ps1
"@
}
