# Restore Docker runtime SOUL + skills from frozen meta backup (Workframe/Workframe/Agents).
# Does NOT touch %LOCALAPPDATA%\hermes or user UUID credential dirs.
$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$Runtime = Join-Path $Root 'runtime\Agents\profiles'
$Meta = (Resolve-Path (Join-Path $Root '..\Workframe\Workframe\Agents\profiles')).Path
$PackSkills = Join-Path $Root 'packages\create-workframe\profiles'

$RuntimeProfiles = @(
  'u-44fb344c-0954-47b6-a-architect',
  'u-cb6a2db4-ac86-4c49-8-architect',
  'u-44fb344c-0954-47b6-a-workframe-agent',
  'u-cb6a2db4-ac86-4c49-8-workframe-agent',
  'u-215ffc8a-3c09-4b5d-8-architect',
  'u-215ffc8a-3c09-4b5d-8-workframe-agent'
)

function Copy-File($from, $to) {
  if (-not (Test-Path $from)) { Write-Warning "missing $from"; return }
  New-Item -ItemType Directory -Force -Path (Split-Path $to -Parent) | Out-Null
  Copy-Item $from $to -Force
  Write-Host "  $to"
}

function Copy-SkillTree($from, $to) {
  if (-not (Test-Path $from)) { return }
  New-Item -ItemType Directory -Force -Path $to | Out-Null
  robocopy $from $to /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
}

Write-Host '=== Template SOUL from meta backup ==='
foreach ($slug in @('architect', 'workframe-agent')) {
  Copy-File (Join-Path $Meta "$slug\SOUL.md") (Join-Path $Runtime "$slug\SOUL.md")
}

Write-Host '=== Per-user runtime SOUL (clone from template) ==='
foreach ($rt in $RuntimeProfiles) {
  if (-not (Test-Path (Join-Path $Runtime $rt))) { continue }
  $template = if ($rt -match '-architect$') { 'architect' } else { 'workframe-agent' }
  Copy-File (Join-Path $Runtime "$template\SOUL.md") (Join-Path $Runtime "$rt\SOUL.md")
}

Write-Host '=== Skills (package seeds; SOUL untouched) ==='
foreach ($skill in @('botfather', 'workframe-cohort', 'kanban-handoff-pattern')) {
  $from = Join-Path $PackSkills "workframe-agent\skills\devops\$skill"
  Copy-SkillTree $from (Join-Path $Runtime "workframe-agent\skills\devops\$skill")
  foreach ($rt in $RuntimeProfiles) {
    if ($rt -match 'workframe-agent$' -and (Test-Path (Join-Path $Runtime $rt))) {
      Copy-SkillTree $from (Join-Path $Runtime "$rt\skills\devops\$skill")
    }
  }
}
$kwFrom = Join-Path $PackSkills 'architect\skills\devops\kanban-worker'
Copy-SkillTree $kwFrom (Join-Path $Runtime 'architect\skills\devops\kanban-worker')
foreach ($rt in $RuntimeProfiles) {
  if ($rt -match '-architect$' -and (Test-Path (Join-Path $Runtime $rt))) {
    Copy-SkillTree $kwFrom (Join-Path $Runtime "$rt\skills\devops\kanban-worker")
  }
}

Write-Host 'Done. Local Hermes + UUID credential dirs NOT touched.'
