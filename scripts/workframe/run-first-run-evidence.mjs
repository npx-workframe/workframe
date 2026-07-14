#!/usr/bin/env node
/**
 * WF-020: FirstRunEvidence — Docker boot, wizard, first chat (redacted credential class only).
 * ponytail: explicit user acknowledgement plus live current-version dogfood probes.
 */
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const pkgRoot = path.join(root, 'packages/create-workframe');
const featureListPath = path.join(root, '.harness/feature_list.json');

const args = process.argv.slice(2);
const userAck = args.includes('--user-ack');
const outIdx = args.indexOf('--output');
const outPath =
  outIdx >= 0
    ? path.resolve(args[outIdx + 1])
    : path.join(root, 'operations/release-evidence/runs/latest-first-run.json');

const commands = [];
const assertions = [];

function run(cmd, cmdArgs, opts = {}) {
  const label = [cmd, ...cmdArgs].join(' ');
  commands.push(label);
  return spawnSync(cmd, cmdArgs, {
    encoding: 'utf8',
    cwd: opts.cwd || root,
    stdio: ['pipe', 'pipe', 'pipe'],
    ...opts,
  });
}

function gitRef() {
  const res = spawnSync('git', ['rev-parse', '--short', 'HEAD'], { encoding: 'utf8', cwd: root });
  return res.status === 0 ? res.stdout.trim() : 'unknown';
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function readEnvPort(projectRoot, key) {
  const envFile = path.join(projectRoot, '.env');
  if (!fs.existsSync(envFile)) return null;
  const line = fs.readFileSync(envFile, 'utf8').split('\n').find((l) => l.startsWith(`${key}=`));
  return line ? line.split('=', 2)[1].trim() : null;
}

function curlOk(url) {
  const res = run('curl', ['-fsS', '--max-time', '8', url], { shell: process.platform === 'win32' });
  return res.status === 0;
}

function curlJson(url) {
  const res = run('curl', ['-fsS', '--max-time', '8', url], { shell: process.platform === 'win32' });
  if (res.status !== 0) return null;
  try {
    return JSON.parse(res.stdout);
  } catch {
    return null;
  }
}

function dockerHealth(container, url) {
  if (!container) return false;
  const code = `import urllib.request; urllib.request.urlopen(${JSON.stringify(url)}, timeout=5).read()`;
  const res = run('docker', ['exec', container, 'python', '-c', code]);
  return res.status === 0;
}

function assertStep(id, ok, note) {
  assertions.push({ id, status: ok ? 'asserted' : 'not_asserted', ...(note ? { note } : {}) });
}

const packageVersion = JSON.parse(fs.readFileSync(path.join(pkgRoot, 'package.json'), 'utf8')).version;

const dogfoodRoot = process.env.WORKFRAME_DOGFOOD_ROOT || path.resolve(root, '..', 'MyBusiness');
const observed = {
  credential_source_class: process.env.WORKFRAME_CREDENTIAL_CLASS || 'byok_user',
  ui_loaded: false,
  api_health_ok: false,
  supervisor_health_ok: false,
  managed_hermes_health_ok: false,
  wizard_completed: false,
  first_chat_stream_ok: false,
  runtime_package_version: null,
  package_version_match: false,
};

if (dogfoodRoot && fs.existsSync(path.join(dogfoodRoot, 'workframe-manifest.json'))) {
  const manifest = readJson(path.join(dogfoodRoot, 'workframe-manifest.json'));
  const apiPort = readEnvPort(dogfoodRoot, 'WORKFRAME_API_PORT') || '19120';
  const uiPort = readEnvPort(dogfoodRoot, 'WORKFRAME_UI_PORT') || '18644';
  const supPort = readEnvPort(dogfoodRoot, 'WORKFRAME_SUPERVISOR_PORT') || '18090';
  const gatewayPort = readEnvPort(dogfoodRoot, 'WORKFRAME_GATEWAY_PORT') || '18642';
  const apiBase = `http://127.0.0.1:${apiPort}`;
  observed.api_health_ok = curlOk(`${apiBase}/api/health`);
  observed.supervisor_health_ok =
    curlOk(`http://127.0.0.1:${supPort}/health`) ||
    dockerHealth(
      manifest?.docker?.containers?.supervisor || `${manifest?.project_slug || 'workframe'}-workframe-supervisor`,
      'http://127.0.0.1:8090/health',
    );
  observed.managed_hermes_health_ok = curlOk(`http://127.0.0.1:${gatewayPort}/health`);
  observed.ui_loaded = curlOk(`http://127.0.0.1:${uiPort}/`);
  const meta = curlJson(`${apiBase}/api/meta`);
  observed.wizard_completed = Boolean(meta);
  observed.runtime_package_version = meta?.package_version || null;
  observed.package_version_match = observed.runtime_package_version === packageVersion;
  commands.push(`curl health probes @ ${dogfoodRoot} (ports ${apiPort}/${uiPort}/${supPort})`);
}

const probeGreen =
  observed.api_health_ok &&
  observed.supervisor_health_ok &&
  observed.managed_hermes_health_ok &&
  observed.ui_loaded &&
  observed.package_version_match;

observed.first_chat_stream_ok = userAck && probeGreen;
assertStep('docker_compose_up', probeGreen, `live probes at ${dogfoodRoot}`);
assertStep('api_health', observed.api_health_ok);
assertStep('supervisor_health', observed.supervisor_health_ok);
assertStep('hermes_health', observed.managed_hermes_health_ok);
assertStep('runtime_package_version', observed.package_version_match, `runtime=${observed.runtime_package_version || 'missing'} expected=${packageVersion}`);
assertStep('wizard_completed', userAck && observed.wizard_completed, 'requires fresh --user-ack after browser wizard/smoke');
assertStep('first_chat_stream', observed.first_chat_stream_ok, 'requires fresh --user-ack after successful chat');
assertStep('session_receipt_minimal', observed.first_chat_stream_ok, 'maintainer dogfood chat');

const allAsserted = assertions.every((a) => a.status === 'asserted');
const evidence = {
  schema_version: '0.1',
  evidence_type: 'first_run',
  gate_name: 'FirstRunGate',
  scenario_id: 'single-user-local-first-chat',
  git_ref: gitRef(),
  package_name: 'create-workframe',
  package_version: packageVersion,
  target_mode: 'single_user_local',
  decision: allAsserted ? 'allow' : 'needs_user_action',
  decision_reason: allAsserted
    ? `Fresh current-version dogfood probes plus explicit user acknowledgement for v${packageVersion}.`
    : `Run current-version dogfood, complete browser wizard/chat, then rerun with WORKFRAME_DOGFOOD_ROOT and --user-ack for v${packageVersion}.`,
  timestamp: new Date().toISOString(),
  commands_redacted: commands.length ? commands : ['live dogfood probes required'],
  observed_outputs_redacted: observed,
  step_assertions: assertions,
};

fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, `${JSON.stringify(evidence, null, 2)}\n`);
console.log(`first-run-evidence: ${evidence.decision} → ${outPath}`);

if (!allAsserted) process.exit(1);
