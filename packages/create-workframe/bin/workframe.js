#!/usr/bin/env node
/**
 * workframe — lifecycle CLI for generated Workframe projects.
 *
 * Commands:
 *   workframe doctor [--repair] [--json]  Diagnose stack; --json mutation-free report
 *   workframe setup      Open Hermes setup (credentials)
 *   workframe stop       Stop all stack containers
 *   workframe start      Start the full stack (docker compose up -d)
 *   workframe restart    Restart the full stack
 *   workframe status     Show running containers
 *   workframe logs       Tail gateway logs
 *   workframe ui         Open Workframe UI in browser
 */
import fs from 'node:fs';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function findProjectRoot() {
  let dir = process.cwd();
  while (true) {
    if (fs.existsSync(path.join(dir, 'workframe-manifest.json'))) return dir;
    if (fs.existsSync(path.join(dir, 'docker-compose.yml')) && fs.existsSync(path.join(dir, '.env'))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

function readManifest(root) {
  const p = path.join(root, 'workframe-manifest.json');
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function readEnvPort(root, key) {
  const envFile = path.join(root, '.env');
  if (!fs.existsSync(envFile)) return null;
  const line = fs.readFileSync(envFile, 'utf8').split('\n').find((l) => l.startsWith(`${key}=`));
  return line ? line.split('=', 2)[1].trim() : null;
}

function dockerCompose(cwd, args, { stdio = 'inherit' } = {}) {
  return spawnSync('docker', ['compose', ...args], { cwd, stdio, encoding: 'utf8' });
}

function doctorAgentDmRuntimes(root, { repair = false } = {}) {
  const fn = repair ? 'doctor_repair_agent_dm_runtimes(repair=True)' : 'doctor_audit_agent_dm_runtimes()';
  const py = `import json, server; print(json.dumps(server.${fn}))`;
  return dockerCompose(root, ['exec', '-T', 'workframe-api', 'python3', '-c', py], { stdio: 'pipe' });
}

function redactPath(root, absolutePath) {
  try {
    const rel = path.relative(root, absolutePath);
    if (!rel || rel.startsWith('..')) return path.basename(absolutePath);
    return rel.split(path.sep).join('/');
  } catch {
    return path.basename(String(absolutePath || ''));
  }
}

function nodeVersion() {
  const res = spawnSync(process.execPath, ['-v'], { encoding: 'utf8' });
  if (res.status !== 0) return null;
  return (res.stdout || res.stderr || '').trim() || null;
}

function buildDoctorJsonReport(root, manifest, issues, checks) {
  const decision = issues.length === 0
    ? 'healthy'
    : checks.docker?.status === 'fail'
      ? 'needs_user_action'
      : 'unhealthy';
  return {
    schema_version: '0.1',
    advisory_only: true,
    decision,
    project: {
      name: manifest?.project_name || path.basename(root),
      package_version: manifest?.package_version || null,
    },
    checks,
    issues,
  };
}

function collectDoctorChecks(root, manifest) {
  const checks = {};
  const issues = [];

  const dockerCheck = spawnSync('docker', ['info'], { encoding: 'utf8' });
  if (dockerCheck.status !== 0) {
    checks.docker = { status: 'fail', note: 'Docker not running or not installed' };
    issues.push('Docker is not running or not installed.');
  } else {
    checks.docker = { status: 'ok', note: 'docker info succeeded' };
  }

  const nodeVer = nodeVersion();
  checks.node = {
    status: nodeVer ? 'ok' : 'skip',
    version: nodeVer,
  };

  if (!manifest) {
    checks.manifest = { status: 'fail', stack: null };
    issues.push('No workframe-manifest.json found.');
  } else {
    checks.manifest = {
      status: 'ok',
      stack: manifest.docker?.stack || null,
    };
  }

  const layout = { workspace: 'missing', runtime: 'missing' };
  for (const dir of ['Files', 'Agents']) {
    if (fs.existsSync(path.join(root, dir))) {
      layout[dir === 'Files' ? 'workspace' : 'runtime'] = 'ok';
    } else {
      issues.push(`${dir}/ directory missing.`);
    }
  }
  checks.layout = { status: layout.workspace === 'ok' && layout.runtime === 'ok' ? 'ok' : 'fail', ...layout };

  checks.cell = {
    deployment_mode: manifest?.security?.deployment_mode || manifest?.deployment_mode || null,
    install_id_redacted: manifest?.install_id ? String(manifest.install_id).slice(0, 8) + '…' : null,
    manifest_path: redactPath(root, path.join(root, 'workframe-manifest.json')),
  };

  const runtimeCandidates = [];
  if (manifest && checks.docker?.status === 'ok') {
    const ps = dockerCompose(root, ['ps', '--format', 'json'], { stdio: 'pipe' });
    if (ps.status === 0 && ps.stdout) {
      try {
        const raw = ps.stdout.trim();
        const containers = raw.startsWith('[')
          ? JSON.parse(raw)
          : raw.split('\n').filter(Boolean).map((line) => JSON.parse(line));
        for (const name of ['gateway', 'workframe-api', 'workframe']) {
          const container = containers.find((c) => c.Name?.includes(name) || c.Service === name);
          runtimeCandidates.push({
            kind: name === 'gateway' ? 'hermes_managed' : 'workframe_service',
            service: name,
            status: container ? (container.State === 'running' ? 'running' : container.State || 'unknown') : 'stopped',
          });
          if (!container || container.State !== 'running') {
            issues.push(`${name} container not running.`);
          }
        }
      } catch {
        runtimeCandidates.push({ kind: 'hermes_managed', service: 'gateway', status: 'unknown' });
      }
    }
  } else {
    runtimeCandidates.push({ kind: 'hermes_managed', service: 'gateway', status: 'unknown', note: 'docker unavailable' });
  }
  checks.runtime_candidates = runtimeCandidates;

  if (!fs.existsSync(path.join(root, '.env'))) {
    issues.push('.env file missing.');
  }
  if (!fs.existsSync(path.join(root, 'docker-compose.yml'))) {
    issues.push('docker-compose.yml missing.');
  }

  return { checks, issues };
}

function cmdDoctor(root, extraArgs = []) {
  const repair = extraArgs.includes('--repair');
  const jsonMode = extraArgs.includes('--json');
  const manifest = readManifest(root);

  if (jsonMode) {
    const { checks, issues } = collectDoctorChecks(root, manifest);
    const report = buildDoctorJsonReport(root, manifest, issues, checks);
    console.log(JSON.stringify(report, null, 2));
    process.exit(report.decision === 'healthy' ? 0 : 1);
    return;
  }

  const issues = [];

  console.log(repair ? 'workframe doctor --repair' : 'workframe doctor');
  console.log('================\n');

  // Check Docker
  const dockerCheck = spawnSync('docker', ['info'], { encoding: 'utf8' });
  if (dockerCheck.status !== 0) {
    issues.push('Docker is not running or not installed.');
    console.log('[FAIL] Docker: not running');
  } else {
    console.log('[ OK] Docker: running');
  }

  // Check manifest
  if (!manifest) {
    issues.push('No workframe-manifest.json found. Are you in a Workframe project?');
    console.log('[FAIL] Manifest: not found');
  } else {
    console.log(`[ OK] Manifest: ${manifest.project_name} (${manifest.docker?.stack})`);
  }

  // Check .env
  const envFile = path.join(root, '.env');
  if (!fs.existsSync(envFile)) {
    issues.push('.env file missing.');
    console.log('[FAIL] .env: missing');
  } else {
    console.log('[ OK] .env: present');
  }

  // Check docker-compose.yml
  const composeFile = path.join(root, 'docker-compose.yml');
  if (!fs.existsSync(composeFile)) {
    issues.push('docker-compose.yml missing.');
    console.log('[FAIL] docker-compose.yml: missing');
  } else {
    console.log('[ OK] docker-compose.yml: present');
  }

  // Check required directories
  for (const dir of ['Agents', 'Files']) {
    if (!fs.existsSync(path.join(root, dir))) {
      issues.push(`${dir}/ directory missing.`);
      console.log(`[FAIL] ${dir}/: missing`);
    } else {
      console.log(`[ OK] ${dir}/: present`);
    }
  }

  // Check containers
  if (manifest && dockerCheck.status === 0) {
    const ps = dockerCompose(root, ['ps', '--format', 'json']);
    if (ps.status === 0 && ps.stdout) {
      try {
        const containers = JSON.parse(ps.stdout);
        const expected = ['gateway', 'dashboard', 'workframe-api', 'workframe'];
        for (const name of expected) {
          const container = containers.find((c) => c.Name?.includes(name) || c.Service === name);
          if (!container) {
            issues.push(`${name} container not found.`);
            console.log(`[FAIL] ${name}: not found`);
          } else if (container.State !== 'running') {
            issues.push(`${name} container is ${container.State}, not running.`);
            console.log(`[FAIL] ${name}: ${container.State}`);
          } else {
            console.log(`[ OK] ${name}: running`);
          }
        }
      } catch {
        // Fallback: plain text parse
        const psPlain = dockerCompose(root, ['ps']);
        console.log('\nContainer status:\n' + psPlain.stdout);
      }
    }
  }

  // Check bootstrap
  if (manifest) {
    const nativeSlug = manifest.native_agent?.profile_slug;
    const soulFile = path.join(root, 'Agents', 'profiles', nativeSlug, 'SOUL.md');
    if (!fs.existsSync(soulFile)) {
      issues.push('Native agent not bootstrapped. Run: ./scripts/bootstrap-native.sh');
      console.log('[FAIL] Bootstrap: native SOUL missing');
    } else {
      console.log('[ OK] Bootstrap: native SOUL present');
    }
  }

  // Check ports
  if (manifest) {
    const ports = manifest.ports;
    if (ports) {
      console.log(`\nPorts:`);
      console.log(`  Gateway: ${ports.gateway}, Dashboard: ${ports.dashboard}, UI: ${ports.ui}, API: ${ports.api}`);
    }
  }

  // Agent DM runtime slots (explicit repair only with --repair)
  if (manifest && dockerCheck.status === 0) {
    const api = dockerCompose(root, ['ps', '--format', 'json'], { stdio: 'pipe' });
    const apiUp = api.status === 0 && (api.stdout || '').includes('workframe-api');
    if (apiUp) {
      const audit = doctorAgentDmRuntimes(root, { repair: false });
      if (audit.status === 0 && audit.stdout) {
        try {
          const data = JSON.parse(audit.stdout.trim().split('\n').pop());
          const missing = data.missing?.length ?? 0;
          if (missing > 0) {
            const msg = `${missing} agent DM runtime profile(s) missing`;
            if (repair) {
              const fixed = doctorAgentDmRuntimes(root, { repair: true });
              if (fixed.status === 0 && fixed.stdout) {
                const result = JSON.parse(fixed.stdout.trim().split('\n').pop());
                const repaired = result.repaired?.length ?? 0;
                const failed = result.failed?.length ?? 0;
                console.log(`[REPAIR] Agent DM runtimes: ${repaired} provisioned, ${failed} failed`);
                if (failed || (result.still_missing?.length ?? 0) > 0) {
                  issues.push(msg);
                }
              } else {
                issues.push(`${msg} (repair failed)`);
                console.log('[FAIL] Agent DM runtime repair failed');
              }
            } else {
              issues.push(`${msg} — run: workframe doctor --repair`);
              console.log(`[WARN] Agent DM runtimes: ${msg}`);
            }
          } else {
            console.log('[ OK] Agent DM runtimes: all provisioned');
          }
        } catch {
          console.log('[skip] Agent DM runtime audit: could not parse API response');
        }
      } else {
        console.log('[skip] Agent DM runtime audit: workframe-api not reachable');
      }
    }
  }

  if (issues.length > 0) {
    console.log(`\n${issues.length} issue(s) found:\n`);
    issues.forEach((i) => console.log(`  - ${i}`));
    process.exit(1);
  } else {
    console.log('\nAll checks passed. Workframe is healthy.');
  }
}

function cmdSetup(root) {
  const manifest = readManifest(root);
  const image = manifest?.docker?.image || 'nousresearch/hermes-agent:latest';
  const name = manifest?.docker?.stack || 'workframe';
  console.log('Opening Hermes setup (interactive)...');
  console.log('Credentials never belong in chat.\n');
  dockerCompose(root, ['pull'], { stdio: 'inherit' });
  const res = spawnSync('docker', [
    'run', '--rm', '-it',
    '--name', `${name}-setup`,
    '--entrypoint', 'hermes',
    '-v', `${path.join(root, 'Agents')}:/opt/data`,
    '-v', `${path.join(root, 'Files')}:/workspace`,
    image, 'setup',
  ], { stdio: 'inherit' });
  if (res.status !== 0) {
    console.error('Setup failed or was cancelled.');
    process.exit(res.status || 1);
  }
}

function cmdStop(root) {
  console.log('Stopping Workframe stack...');
  const res = dockerCompose(root, ['down']);
  if (res.status !== 0) {
    console.error('Failed to stop stack.');
    process.exit(1);
  }
  console.log('Stack stopped.');
}

function cmdStart(root) {
  console.log('Starting Workframe stack...');
  const res = dockerCompose(root, ['up', '-d']);
  if (res.status !== 0) {
    console.error('Failed to start stack.');
    process.exit(1);
  }
  const manifest = readManifest(root);
  if (manifest?.ports) {
    console.log(`\nWorkframe UI: http://127.0.0.1:${manifest.ports.ui}/`);
    console.log(`Hermes chat:  http://127.0.0.1:${manifest.ports.dashboard}/chat`);
  }
  console.log('Stack started.');
}

function cmdRestart(root) {
  console.log('Restarting Workframe stack...');
  const res = dockerCompose(root, ['restart']);
  if (res.status !== 0) {
    console.error('Failed to restart stack.');
    process.exit(1);
  }
  console.log('Stack restarted.');
}

function cmdStatus(root) {
  dockerCompose(root, ['ps'], { stdio: 'inherit' });
}

function cmdLogs(root, args) {
  const follow = args.includes('--follow') || args.includes('-f');
  const composeArgs = ['logs'];
  if (follow) composeArgs.push('--follow');
  composeArgs.push('gateway');
  dockerCompose(root, composeArgs, { stdio: 'inherit' });
}

function cmdUi(root) {
  const manifest = readManifest(root);
  const port = readEnvPort(root, 'WORKFRAME_UI_PORT') || manifest?.ports?.ui || '18644';
  const url = `http://127.0.0.1:${port}/`;
  console.log(`Opening Workframe UI: ${url}`);
  const openCmd = process.platform === 'win32' ? 'start' : process.platform === 'darwin' ? 'open' : 'xdg-open';
  const child = spawn(openCmd, [url], { detached: true, stdio: 'ignore' });
  child.unref();
}

function usage() {
  console.log(`workframe — lifecycle CLI for Workframe projects

Usage:
  workframe doctor [--repair] [--json]  Diagnose stack; --json mutation-free report
  workframe setup               Open Hermes setup (credentials)
  workframe start               Start the full stack (docker compose up -d)
  workframe stop                Stop all stack containers
  workframe restart             Restart the full stack
  workframe status              Show running containers
  workframe logs [--follow]     Tail gateway logs
  workframe ui                  Open Workframe UI in browser

Run from a Workframe project directory (where workframe-manifest.json lives).
`);
}

const args = process.argv.slice(2);
const command = args[0];
const extraArgs = args.slice(1);

const root = findProjectRoot();
if (!root) {
  console.error('ERROR: Not in a Workframe project. No workframe-manifest.json found.');
  process.exit(1);
}

switch (command) {
  case 'doctor':   cmdDoctor(root, extraArgs); break;
  case 'setup':    cmdSetup(root); break;
  case 'stop':     cmdStop(root); break;
  case 'start':    cmdStart(root); break;
  case 'restart':  cmdRestart(root); break;
  case 'status':   cmdStatus(root); break;
  case 'logs':     cmdLogs(root, extraArgs); break;
  case 'ui':       cmdUi(root); break;
  case '--help':
  case '-h':
  case 'help':     usage(); break;
  default:
    if (command) console.error(`Unknown command: ${command}`);
    usage();
    process.exit(command ? 1 : 0);
}
