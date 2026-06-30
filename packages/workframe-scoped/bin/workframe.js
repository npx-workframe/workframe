#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

function findProjectRoot(start = process.cwd()) {
  let dir = path.resolve(start);
  while (true) {
    if (fs.existsSync(path.join(dir, 'workframe-manifest.json'))) return { root: dir, manifestDir: dir };
    if (fs.existsSync(path.join(dir, 'Workframe', 'workframe-manifest.json'))) {
      return { root: dir, manifestDir: path.join(dir, 'Workframe') };
    }
    const parent = path.dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

function icon(ok) {
  return ok ? '[ok]' : '[fail]';
}

function printCheck(name, ok, detail = '') {
  console.log(`  ${icon(ok)} ${name}${detail ? `: ${detail}` : ''}`);
  return ok;
}

function printSkip(name, detail = '') {
  console.log(`  [skip] ${name}${detail ? `: ${detail}` : ''}`);
}

function run(cmd, args, cwd) {
  const res = spawnSync(cmd, args, { encoding: 'utf8', cwd });
  return {
    ok: res.status === 0,
    code: res.status ?? 1,
    out: (res.stdout || '').trim(),
    err: (res.stderr || '').trim(),
  };
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function readText(file) {
  return fs.readFileSync(file, 'utf8');
}

function exists(root, rel) {
  return fs.existsSync(path.join(root, rel));
}

function relList(items) {
  return items.length ? items.join(', ') : 'none';
}

function countServices(composeText) {
  const lines = composeText.split(/\r?\n/);
  let inServices = false;
  let count = 0;
  for (const line of lines) {
    if (!inServices) {
      if (line.trim() === 'services:') inServices = true;
      continue;
    }
    if (/^[A-Za-z]/.test(line)) break;
    if (/^  [A-Za-z0-9_-]+:\s*$/.test(line)) count += 1;
  }
  return count;
}

function extractContainerNames(composeText) {
  return [...composeText.matchAll(/container_name:\s*([^\s]+)/g)].map((m) => m[1]);
}

function doctor() {
  const located = findProjectRoot();
  if (!located) {
    console.error('Not in a Workframe project (workframe-manifest.json not found).');
    process.exit(1);
  }
  const root = located.root;
  const manifestDir = located.manifestDir;

  console.log(`Workframe doctor - ${root}\n`);

  let pass = 0;
  let total = 0;
  const tally = (ok) => {
    total += 1;
    if (ok) pass += 1;
    return ok;
  };

  const manifestPath = path.join(manifestDir, 'workframe-manifest.json');
  let manifest = null;
  try {
    manifest = readJson(manifestPath);
    tally(printCheck('workframe-manifest.json', true));
  } catch (err) {
    tally(printCheck('workframe-manifest.json', false, `invalid JSON: ${err.message}`));
    console.log(`\n${pass}/${total} checks passed.`);
    process.exit(1);
  }

  const projectName = manifest.project_name || 'Unknown';
  const nativeSlug = manifest.native_agent?.profile_slug || 'workframe-agent';
  const nativeName = manifest.native_agent?.display_name || 'Workframe Agent';
  const stack = manifest.docker?.stack || path.basename(root).toLowerCase();
  const bootstrapDefault = manifest.bootstrap?.default || 'unknown';
  const installedAfterNative = manifest.profiles_installed_after_native_bootstrap || [];
  const specialistCatalog = manifest.profiles_catalog || [];

  console.log(`  Project: ${projectName}`);
  console.log(`  Native agent: ${nativeName} (${nativeSlug})`);
  console.log(`  Pack: ${manifest.pack || 'unknown'}`);
  console.log(`  Bootstrap default: ${bootstrapDefault}`);
  console.log(`  Native bootstrap installs: ${relList(installedAfterNative)}`);
  console.log(`  Specialist catalog: ${relList(specialistCatalog)}\n`);

  tally(printCheck('Agents/', exists(root, 'Agents')));
  tally(printCheck('Files/', exists(root, 'Files')));
  tally(printCheck('Files/AGENTS.md', exists(root, 'Files/AGENTS.md')));
  tally(printCheck('Files/.hermes.md', exists(root, 'Files/.hermes.md')));
  tally(printCheck('Workframe/SETUP.md', exists(root, 'Workframe/SETUP.md')));
  tally(printCheck('Workframe/docker-compose.yml', exists(root, 'Workframe/docker-compose.yml')));
  tally(printCheck('Workframe/scripts/agent-lifecycle.mjs', exists(root, 'Workframe/scripts/agent-lifecycle.mjs')));
  tally(printCheck('Workframe/scripts/lib/workframe-registry.mjs', exists(root, 'Workframe/scripts/lib/workframe-registry.mjs')));

  const nativeSeedSoul = exists(root, `Workframe/scripts/seed/profiles/${nativeSlug}/SOUL.md`);
  const nativeSeedSetup = exists(root, `Workframe/scripts/seed/profiles/${nativeSlug}/SETUP.md`);
  tally(printCheck('Native SOUL seed', nativeSeedSoul, nativeSeedSoul ? nativeSlug : 'missing native seed SOUL'));
  tally(printCheck('Native SETUP seed', nativeSeedSetup, nativeSeedSetup ? nativeSlug : 'missing native setup playbook'));

  tally(printCheck('Bootstrap default is native', bootstrapDefault === 'native', bootstrapDefault));
  tally(
    printCheck(
      'Native-only installed-after-bootstrap set',
      installedAfterNative.length === 1 && installedAfterNative[0] === nativeSlug,
      relList(installedAfterNative),
    ),
  );
  tally(printCheck('Specialist catalog present', specialistCatalog.length > 0, relList(specialistCatalog)));

  const composePath = path.join(root, 'Workframe', 'docker-compose.yml');
  const composeText = exists(root, 'Workframe/docker-compose.yml') ? readText(composePath) : '';
  if (composeText) {
    tally(printCheck('Compose service count is 4', countServices(composeText) === 4, `${countServices(composeText)} services`));
    tally(printCheck('Compose mounts workframe-api', composeText.includes('./workframe-api/public:/app/public:ro')));
    tally(printCheck('Compose mounts Workframe UI', composeText.includes('WORKFRAME_UI_STATIC_DIR') || composeText.includes('./workframe-ui/public:/usr/share/nginx/html:ro')));
    tally(
      printCheck(
        'Gateway uses native profile',
        composeText.includes(`"-p", "${nativeSlug}"`) || composeText.includes(`-p ${nativeSlug} gateway run`),
        nativeSlug,
      ),
    );
    tally(printCheck('Gateway enables dashboard TUI', composeText.includes('HERMES_DASHBOARD_TUI=1')));
    tally(printCheck('No profile dashboard services', !composeText.includes('dashboard-dev:') && !composeText.includes('/hermes-profiles/')));
    tally(printCheck('Gateway creates avatar/user dirs', composeText.includes('/workspace/User') && composeText.includes('/opt/data/Avatars')));
    const containers = extractContainerNames(composeText);
    tally(printCheck('Named core containers', containers.includes(`${stack}-gateway`) && containers.includes(`${stack}-dashboard`) && containers.includes(`${stack}-workframe-api`) && containers.includes(`${stack}-workframe`), relList(containers)));
  }

  const wfReadme = path.join(root, 'Workframe', 'README.md');
  if (fs.existsSync(wfReadme)) {
    const txt = readText(wfReadme);
    tally(printCheck('Project README references Workframe UI', txt.includes('Workframe UI')));
  }

  const dockerInfo = run('docker', ['info'], root);
  tally(printCheck('Docker daemon', dockerInfo.ok, dockerInfo.ok ? 'reachable' : (dockerInfo.err || 'not running')));

  if (dockerInfo.ok && composeText) {
    const agentsEnv = path.join(root, 'Agents', '.env');
    if (!fs.existsSync(agentsEnv)) {
      printSkip('docker compose config', 'run Hermes setup first to create Agents/.env');
      printSkip('Four compose containers running', 'stack not expected before bootstrap');
      printSkip('Compose containers healthy/running', 'stack not expected before bootstrap');
    } else {
      const composeConfig = run('docker', ['compose', '-f', composePath, 'config'], root);
      tally(printCheck('docker compose config', composeConfig.ok, composeConfig.ok ? 'valid' : composeConfig.err));

      const composePs = run('docker', ['compose', '-f', composePath, 'ps', '--format', 'json'], root);
      if (composePs.ok) {
        const rows = composePs.out
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter(Boolean)
          .map((line) => {
            try {
              return JSON.parse(line);
            } catch {
              return null;
            }
          })
          .filter(Boolean);
        const names = rows.map((row) => row.Name);
        tally(printCheck('Four compose containers running', rows.length === 4, relList(names)));
        const allRunning = rows.every((row) => String(row.State || '').toLowerCase() === 'running');
        tally(printCheck('Compose containers healthy/running', allRunning, rows.map((row) => `${row.Name}:${row.State}`).join(', ')));
      } else {
        tally(printCheck('docker compose ps', false, composePs.err || composePs.out));
      }
    }
  }

  console.log(`\n${pass}/${total} checks passed.`);
  if (pass < total) process.exit(1);
}

function setup() {
  const located = findProjectRoot();
  if (!located) {
    console.error('Not in a Workframe project.');
    process.exit(1);
  }
  const root = located.root;
  const setupDoc = path.join(root, 'Workframe', 'SETUP.md');
  if (fs.existsSync(setupDoc)) {
    console.log(fs.readFileSync(setupDoc, 'utf8'));
  } else {
    console.log('Open Workframe/SETUP.md for onboarding steps.');
  }
}

function usage() {
  console.log(`workframe - lifecycle CLI for existing Workframe projects

Commands:
  workframe doctor     Validate native-first layout, compose topology, and runtime state
  workframe setup      Print onboarding steps from Workframe/SETUP.md
  workframe help       Show this help
`);
}

const [, , cmd] = process.argv;
switch (cmd) {
  case 'doctor':
    doctor();
    break;
  case 'setup':
    setup();
    break;
  case 'help':
  case '--help':
  case '-h':
  case undefined:
    usage();
    break;
  default:
    console.error(`Unknown command: ${cmd}`);
    usage();
    process.exit(1);
}
