import path from 'node:path';
import os from 'node:os';

export function recommendArchitectonicPreset(draft) {
  const surface = String(draft.execution_surface?.value || '').toLowerCase();
  if (surface.includes('workframe') || surface.includes('hermes') || surface.includes('cell')) {
    return 'project-system';
  }
  return 'project+knowledge+skills';
}

export function buildArchitectonicPlan(draft, options = {}) {
  const targetRoot = options.targetRoot || path.join(os.homedir(), 'architectonic-workspace');
  const preset = recommendArchitectonicPreset(draft);
  const entityName = draft.entity?.value || 'workspace';

  const files = [
    'architectonic.json',
    'AGENTS.md',
    'ONBOARDING.md',
    'README.md',
    'organization/README.md',
    'organization/open-questions.md',
    'organization/decisions.md',
    'organization/constitution.md',
    'organization/doctrine.md',
    'organization/identity.md',
    'organization/project.md',
    'operations/ledger.json',
  ];

  return {
    schema_version: '0.1',
    mode: 'architectonic_composition_plan',
    dry_run: true,
    target_root: targetRoot,
    preset,
    entity_name: entityName,
    proposed_files: files.map((rel) => path.join(targetRoot, rel)),
    actions: files.map((rel) => ({
      path: path.join(targetRoot, rel),
      action: 'add_if_missing',
      overwrite: false,
    })),
    collisions: [],
    mutations: [],
    command: `npx architectonic init ${entityName} --preset ${preset} --source npm`,
  };
}

export function buildDeploymentPlan(draft, statusReport, architectonicPlan) {
  const wantsWorkframe = String(draft.execution_surface?.value || '').toLowerCase().match(/workframe|hermes|cell|team|multi/);
  const docker = statusReport.system.find((item) => item.id === 'docker');
  const hasDocker = docker?.status === 'verified' || docker?.status === 'detected';

  if (!wantsWorkframe) {
    return {
      schema_version: '0.1',
      mode: 'deployment_plan',
      dry_run: true,
      recommendation: 'architectonic_only',
      workframe_install: false,
      hermes_required: false,
      notes: ['No Workframe cell requested. KB lives in Architectonic workspace files.'],
      mutations: [],
    };
  }

  return {
    schema_version: '0.1',
    mode: 'deployment_plan',
    dry_run: true,
    recommendation: hasDocker ? 'create_workframe_docker' : 'install_docker_then_create_workframe',
    workframe_install: true,
    hermes_required: true,
    kb_mount: 'Files/ (workspace truth)',
    runtime_mount: 'Agents/ (/opt/data)',
    command: 'npx create-workframe@latest MyProject',
    docker_required: !hasDocker,
    architectonic_target: architectonicPlan.target_root,
    mutations: [],
  };
}
