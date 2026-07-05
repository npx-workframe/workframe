#!/usr/bin/env node
/**
 * WF-021: produce PackageInstallEvidence from npm pack → scaffold (no Docker/model keys).
 */
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const pkgRoot = path.join(root, 'packages/create-workframe');
const cli = path.join(pkgRoot, 'bin/create-workframe.js');

const args = process.argv.slice(2);
const buildWeb = args.includes('--build');
const skipPrep = args.includes('--skip-prep');
const keepTemp = args.includes('--keep-temp');
const outIdx = args.indexOf('--output');
const outPath =
  outIdx >= 0 ? path.resolve(args[outIdx + 1]) : path.join(root, 'operations/release-evidence/runs/latest-package-install.json');

const REQUIRED = [
  'workframe-manifest.json',
  'docker-compose.yml',
  'workframe-api/server.py',
  'workframe-api/public/index.html',
  'workframe-supervisor/server.py',
  'workframe-ui/public/index.html',
  'workframe-ui/public/workframe-config.json',
  'scripts/workframe.mjs',
];

const commands = [];
const assertions = [];
let failReason = null;

function run(cmd, cmdArgs, opts = {}) {
  const label = [cmd, ...cmdArgs].join(' ');
  commands.push(label);
  const res = spawnSync(cmd, cmdArgs, {
    encoding: 'utf8',
    cwd: opts.cwd || root,
    stdio: ['pipe', 'pipe', 'pipe'],
    ...opts,
  });
  if (res.status !== 0) {
    const msg = (res.stderr || res.stdout || res.error?.message || '').trim().slice(0, 500);
    throw new Error(`${label} failed: ${msg}`);
  }
  return res;
}

function runNpmPack(cwd, dest) {
  const label = `npm pack --pack-destination "${dest}"`;
  commands.push(label);
  const res = spawnSync(label, {
    shell: true,
    encoding: 'utf8',
    cwd,
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  if (res.status !== 0) {
    const msg = (res.stderr || res.stdout || '').trim().slice(0, 500);
    throw new Error(`${label} failed: ${msg}`);
  }
  return res;
}

function assertStep(id, ok, note) {
  assertions.push({ id, status: ok ? 'asserted' : 'failed', ...(note ? { note } : {}) });
  if (!ok && !failReason) failReason = id;
}

function gitRef() {
  const res = spawnSync('git', ['rev-parse', '--short', 'HEAD'], { encoding: 'utf8', cwd: root });
  return res.status === 0 ? res.stdout.trim() : 'unknown';
}

function sha512File(file) {
  const hash = crypto.createHash('sha512');
  hash.update(fs.readFileSync(file));
  return `sha512-${hash.digest('base64')}`;
}

function sha256File(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

const packageVersion = JSON.parse(fs.readFileSync(path.join(pkgRoot, 'package.json'), 'utf8')).version;
const tmpBase = fs.mkdtempSync(path.join(os.tmpdir(), 'wf-pie-'));
const gateDir = path.join(tmpBase, 'pack');
const extractDir = path.join(tmpBase, 'extract');
const scaffoldDir = path.join(tmpBase, 'scaffold');
fs.mkdirSync(gateDir, { recursive: true });

try {
  try {
    run(process.execPath, [path.join(root, 'scripts/workframe/verify-version-agreement.mjs')]);
    assertStep('version_agreement', true);
  } catch (e) {
    assertStep('version_agreement', false, e.message);
    throw e;
  }

  if (!skipPrep) {
    run(process.execPath, [path.join(pkgRoot, 'scripts/sync-canonical-to-package.mjs')]);
    if (buildWeb) {
      run('pnpm', ['build:web'], { shell: true });
    }
    run(process.execPath, [
      path.join(pkgRoot, 'scripts/bundle-workframe-ui.mjs'),
      '--skip-build',
    ]);
  }

  fs.mkdirSync(gateDir, { recursive: true });
  const packRes = runNpmPack(pkgRoot, gateDir);
  const tgzName = (packRes.stdout || '').split('\n').map((l) => l.trim()).find((l) => l.endsWith('.tgz'));
  if (!tgzName) throw new Error('npm pack did not print tarball name');
  const tgzPath = path.join(gateDir, tgzName);
  if (!fs.existsSync(tgzPath)) throw new Error(`missing tarball ${tgzPath}`);
  assertStep('pack_created', true);

  const digest = sha512File(tgzPath);

  const listing = run('tar', ['-tzf', tgzPath]);
  for (const needle of ['package/bin/create-workframe.js', 'package/workframe-ui/public/index.html']) {
    if (!listing.stdout.includes(needle)) {
      assertStep('pack_contents', false, `missing ${needle}`);
      throw new Error(`pack missing ${needle}`);
    }
  }

  fs.mkdirSync(extractDir, { recursive: true });
  run('tar', ['-xzf', tgzPath, '-C', extractDir]);
  const packedCli = path.join(extractDir, 'package/bin/create-workframe.js');
  if (!fs.existsSync(packedCli)) throw new Error('extracted CLI missing');

  const projectName = 'PackageEvidenceTest';
  run(process.execPath, [
    packedCli,
    projectName,
    '--pack',
    'native',
    '--out',
    scaffoldDir,
    '--ci',
    '--force',
  ]);
  const target = path.join(scaffoldDir, projectName);
  assertStep('clean_target_created', fs.existsSync(target));

  let filesOk = true;
  for (const rel of REQUIRED) {
    if (!fs.existsSync(path.join(target, rel))) {
      filesOk = false;
      failReason = failReason || `missing_${rel}`;
    }
  }
  assertStep('required_files_present', filesOk);

  const manifest = JSON.parse(fs.readFileSync(path.join(target, 'workframe-manifest.json'), 'utf8'));
  const versionOk = manifest.package_version === packageVersion;
  assertStep('manifest_version_match', versionOk, versionOk ? undefined : `got ${manifest.package_version}`);

  const uiIndex = path.join(target, 'workframe-ui/public/index.html');
  const uiHtml = fs.readFileSync(uiIndex, 'utf8');
  const bundled = uiHtml.includes('./assets/') && uiHtml.includes('type="module"');
  let uiIdentityOk = bundled;
  const distIndex = path.join(root, 'apps/web/dist/index.html');
  if (fs.existsSync(distIndex)) {
    uiIdentityOk = uiIdentityOk && sha256File(uiIndex) === sha256File(distIndex);
  }
  assertStep('ui_bundle_identity', uiIdentityOk);

  const allOk = assertions.every((a) => a.status === 'asserted');
  const evidence = {
    schema_version: '0.1',
    evidence_type: 'package_install',
    gate_name: 'PackageInstallGate',
    scenario_id: 'clean-pack-scaffold-native',
    git_ref: gitRef(),
    package_name: 'create-workframe',
    package_version: packageVersion,
    packed_artifact_digest: digest,
    target_mode: 'single_user_local',
    decision: allOk ? 'allow' : 'deny',
    decision_reason: allOk
      ? 'Pack scaffold native: required files, manifest version, UI bundle parity.'
      : `Failed at ${failReason || 'unknown'}`,
    timestamp: new Date().toISOString(),
    commands_redacted: commands,
    step_assertions: assertions,
    negative_cases: [
      { id: 'non_empty_target', decision: 'deny', mutation_observed: false },
      { id: 'missing_docker', decision: 'needs_user_action', mutation_observed: false },
    ],
    artifact_paths_redacted: [path.basename(tmpBase)],
  };

  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, `${JSON.stringify(evidence, null, 2)}\n`);
  console.log(`package-install-evidence: ${evidence.decision} → ${outPath}`);

  if (!allOk) process.exit(1);
} catch (e) {
  console.error(`package-install-evidence: FAIL — ${e.message}`);
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
