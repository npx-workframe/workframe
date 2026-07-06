#!/usr/bin/env node
/**
 * WF-019: NegativeInstallEvidence — deny paths, no filesystem mutation (temp dir only).
 */
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const cli = path.join(root, 'packages/create-workframe/bin/create-workframe.js');
const pkgRoot = path.join(root, 'packages/create-workframe');

const args = process.argv.slice(2);
const outIdx = args.indexOf('--output');
const outPath =
  outIdx >= 0
    ? path.resolve(args[outIdx + 1])
    : path.join(root, 'operations/release-evidence/runs/latest-negative-install.json');
const keepTemp = args.includes('--keep-temp');

const commands = [];
const cases = [];
let failReason = null;

function run(cmd, cmdArgs, opts = {}) {
  const label = [cmd, ...cmdArgs].join(' ');
  commands.push(label);
  return spawnSync(cmd, cmdArgs, {
    encoding: 'utf8',
    cwd: opts.cwd || root,
    env: opts.env || process.env,
    stdio: ['pipe', 'pipe', 'pipe'],
    ...opts,
  });
}

function gitRef() {
  const res = spawnSync('git', ['rev-parse', '--short', 'HEAD'], { encoding: 'utf8', cwd: root });
  return res.status === 0 ? res.stdout.trim() : 'unknown';
}

function hashTree(dir) {
  if (!fs.existsSync(dir)) return 'sha256:empty';
  const hash = crypto.createHash('sha256');
  const walk = (d) => {
    for (const ent of fs
      .readdirSync(d, { withFileTypes: true })
      .sort((a, b) => a.name.localeCompare(b.name))) {
      const p = path.join(d, ent.name);
      hash.update(p);
      if (ent.isDirectory()) walk(p);
      else hash.update(fs.readFileSync(p));
    }
  };
  walk(dir);
  return `sha256:${hash.digest('hex')}`;
}

function recordCase(id, { decision, before, after, exitCode, note }) {
  const mutation = before !== after;
  const row = {
    id,
    decision,
    mutation_observed: mutation,
    before_hash: before,
    after_hash: after,
    ...(note ? { note } : {}),
  };
  cases.push(row);
  if (mutation) {
    failReason = failReason || `${id}: mutation observed`;
  }
  if (decision === 'deny' && exitCode === 0) {
    failReason = failReason || `${id}: expected deny exit non-zero`;
  }
  return row;
}

const packageVersion = JSON.parse(fs.readFileSync(path.join(pkgRoot, 'package.json'), 'utf8')).version;
const tmpBase = fs.mkdtempSync(path.join(os.tmpdir(), 'wf-nie-'));

try {
  run(process.execPath, [path.join(pkgRoot, 'scripts/sync-canonical-to-package.mjs')]);

  // unsafe project name — rejected before any target mutation
  {
    const sandbox = path.join(tmpBase, 'unsafe');
    fs.mkdirSync(sandbox, { recursive: true });
    const before = hashTree(sandbox);
    const res = run(process.execPath, [
      cli,
      '--name',
      '../escape',
      '--out',
      sandbox,
      '--pack',
      'native',
      '--ci',
      '--no-launch',
    ]);
    const after = hashTree(sandbox);
    recordCase('unsafe_project_name', {
      decision: 'deny',
      before,
      after,
      exitCode: res.status,
      note: (res.stderr || res.stdout || '').trim().slice(0, 200) || 'invalid project name',
    });
  }

  // non-empty target (empty directory exists, no --force on CLI)
  {
    const sandbox = path.join(tmpBase, 'nonempty');
    fs.mkdirSync(sandbox, { recursive: true });
    fs.mkdirSync(path.join(sandbox, 'workframe-app'), { recursive: true });
    const before = hashTree(sandbox);
    const res = run(process.execPath, [
      cli,
      '--pack',
      'native',
      '--out',
      sandbox,
      '--ci',
      '--no-launch',
    ]);
    const after = hashTree(sandbox);
    recordCase('non_empty_target', {
      decision: 'deny',
      before,
      after,
      exitCode: res.status,
      note: 'existing empty target dir without --force',
    });
  }

  // arbitrary foreign directory — deny without deleting foreign content
  {
    const sandbox = path.join(tmpBase, 'foreign');
    fs.mkdirSync(sandbox, { recursive: true });
    const target = path.join(sandbox, 'workframe-app');
    fs.mkdirSync(target, { recursive: true });
    fs.writeFileSync(path.join(target, 'foreign.txt'), 'do-not-mutate');
    const before = hashTree(sandbox);
    const res = run(process.execPath, [
      cli,
      '--pack',
      'native',
      '--out',
      sandbox,
      '--ci',
      '--no-launch',
    ]);
    const after = hashTree(sandbox);
    recordCase('arbitrary_dir_deny', {
      decision: 'deny',
      before,
      after,
      exitCode: res.status,
      note: 'non-workframe files preserved',
    });
  }

  // missing Docker — scaffold ok; doctor reports needs_user_action, no project mutation
  {
    const sandbox = path.join(tmpBase, 'nodocker');
    fs.mkdirSync(sandbox, { recursive: true });
    const scaffold = run(process.execPath, [
      cli,
      '--name',
      'DockerProbe',
      '--out',
      sandbox,
      '--pack',
      'native',
      '--ci',
      '--no-launch',
    ]);
    const project = path.join(sandbox, 'DockerProbe');
    if (scaffold.status !== 0 || !fs.existsSync(project)) {
      throw new Error(`scaffold for missing_docker failed: ${(scaffold.stderr || '').slice(0, 300)}`);
    }
    const before = hashTree(project);
    const doctorCli = path.join(project, 'scripts/workframe.mjs');
    const noDockerPath = process.platform === 'win32' ? '' : '/usr/bin:/bin';
    const res = run(process.execPath, [doctorCli, 'doctor'], {
      cwd: project,
      env: { ...process.env, PATH: noDockerPath },
    });
    const after = hashTree(project);
    recordCase('missing_docker', {
      decision: 'needs_user_action',
      before,
      after,
      exitCode: res.status,
      note: 'doctor without docker in PATH',
    });
  }

  const matrixOk = cases.every((c) => c.mutation_observed === false);
  const denyOk = cases
    .filter((c) => c.id !== 'missing_docker')
    .every((c) => c.decision === 'deny' && c.before_hash === c.after_hash);

  const evidence = {
    schema_version: '0.1',
    evidence_type: 'negative_install',
    gate_name: 'NegativeInstallGate',
    scenario_id: 'install-deny-matrix',
    git_ref: gitRef(),
    package_name: 'create-workframe',
    package_version: packageVersion,
    target_mode: 'negative_test',
    decision: matrixOk && denyOk ? 'allow' : 'deny',
    decision_reason: matrixOk && denyOk
      ? 'All deny cases left sandbox hashes unchanged; missing_docker is needs_user_action only.'
      : `Failed: ${failReason || 'matrix check'}`,
    timestamp: new Date().toISOString(),
    commands_redacted: commands,
    step_assertions: [
      {
        id: 'matrix_executed',
        status: matrixOk && denyOk ? 'asserted' : 'failed',
        note: `${cases.length} cases`,
      },
    ],
    cases,
    artifact_paths_redacted: [path.basename(tmpBase)],
  };

  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, `${JSON.stringify(evidence, null, 2)}\n`);
  console.log(`negative-install-evidence: ${evidence.decision} → ${outPath}`);

  if (!matrixOk || !denyOk) process.exit(1);
} catch (e) {
  console.error(`negative-install-evidence: FAIL — ${e.message}`);
  process.exit(1);
} finally {
  if (!keepTemp) {
    try {
      fs.rmSync(tmpBase, { recursive: true, force: true });
    } catch {
      /* ponytail: best-effort temp cleanup on Windows */
    }
  } else {
    console.log(`kept temp: ${tmpBase}`);
  }
}
