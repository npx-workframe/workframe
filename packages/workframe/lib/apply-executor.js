import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import process from 'node:process';
import { writeOrganizationFromDraft, linkOrganizationToWorkframeFiles } from './organization-write.js';
import { firstLine } from './runtime.js';

function runNpx(args, options = {}) {
  const result = spawnSync('npx', args, {
    encoding: 'utf8',
    cwd: options.cwd,
    env: process.env,
    shell: process.platform === 'win32',
    windowsHide: true,
    timeout: options.timeout ?? 600_000,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  return {
    ok: result.status === 0 && !result.error,
    code: result.status ?? 1,
    stdout: String(result.stdout ?? '').trim(),
    stderr: String(result.stderr ?? '').trim(),
    error: result.error ? String(result.error.message || result.error) : '',
  };
}

export function preflightApply(bundle) {
  const workspaceRoot = bundle.architectonic.target_root;
  const collisions = [];
  if (fs.existsSync(workspaceRoot)) {
    const entries = fs.readdirSync(workspaceRoot);
    if (entries.length > 0) {
      collisions.push({ path: workspaceRoot, reason: 'directory_not_empty', entries: entries.slice(0, 8) });
    }
  }
  return { ok: collisions.length === 0, collisions, workspace_root: workspaceRoot };
}

export function executeApply(bundle, draft) {
  const mutations = [];
  const preflight = preflightApply(bundle);
  if (!preflight.ok) {
    return { ok: false, reason: 'preflight_failed', preflight, mutations };
  }

  const workspaceRoot = bundle.architectonic.target_root;
  const parentDir = path.dirname(workspaceRoot);
  const workspaceName = path.basename(workspaceRoot);
  const preset = bundle.architectonic.preset;

  fs.mkdirSync(parentDir, { recursive: true });

  const init = runNpx([
    'architectonic@latest', 'init', workspaceName,
    '--preset', preset,
    '--source', 'npm',
    '--dir', parentDir,
  ]);

  if (!init.ok) {
    return {
      ok: false,
      reason: 'architectonic_init_failed',
      detail: firstLine(init.stderr || init.stdout || init.error),
      mutations,
    };
  }
  if (!fs.existsSync(path.join(workspaceRoot, 'organization'))) {
    return {
      ok: false,
      reason: 'architectonic_init_incomplete',
      detail: firstLine(init.stderr || init.stdout || 'organization folder missing'),
      mutations,
    };
  }
  mutations.push({ type: 'architectonic_init', path: workspaceRoot, preset });

  const onboard = runNpx(['architectonic@latest', 'onboard', '--fix', '--dir', workspaceRoot]);
  if (onboard.ok) mutations.push({ type: 'architectonic_onboard_fix', path: workspaceRoot });

  const orgWrite = writeOrganizationFromDraft(workspaceRoot, draft);
  mutations.push({ type: 'organization_write', paths: orgWrite.written });

  if (bundle.deployment.workframe_install) {
    const cellName = 'workframe-cell';
    const create = runNpx([
      'create-workframe@latest', cellName,
      '--yes',
      '--out', workspaceRoot,
    ], { timeout: 900_000 });

    if (!create.ok) {
      return {
        ok: false,
        reason: 'create_workframe_failed',
        detail: firstLine(create.stderr || create.stdout || create.error),
        mutations,
        partial: { architectonic: workspaceRoot },
      };
    }
    const cellRoot = path.join(workspaceRoot, cellName);
    mutations.push({ type: 'create_workframe', path: cellRoot, name: cellName });

    const link = linkOrganizationToWorkframeFiles(cellRoot, workspaceRoot);
    mutations.push({ type: 'link_kb_to_files', ...link });
  }

  return {
    ok: true,
    workspace_root: workspaceRoot,
    mutations,
    next_steps: bundle.deployment.workframe_install
      ? [
        `cd ${path.join(workspaceRoot, 'workframe-cell')} && docker compose up -d`,
        'Open the wizard URL from create-workframe output',
        'Organization KB is mirrored under Files/organization',
      ]
      : [
        `cd ${workspaceRoot}`,
        'npx architectonic onboard',
        'npx architectonic verify',
      ],
  };
}
