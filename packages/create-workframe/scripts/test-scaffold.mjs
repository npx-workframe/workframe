#!/usr/bin/env node
/**
 * Dev/CI smoke test: generate all packs and verify required scaffold files.
 * Canonical installer: bin/create-workframe.js
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PKG_ROOT = path.resolve(__dirname, '..');
const SYNC = path.join(PKG_ROOT, 'scripts', 'sync-canonical-to-package.mjs');
const CLI = path.join(PKG_ROOT, 'bin', 'create-workframe.js');

const syncRes = spawnSync(process.execPath, [SYNC], { encoding: 'utf8', cwd: PKG_ROOT });
if (syncRes.status !== 0) {
  console.error(syncRes.stderr || syncRes.stdout);
  process.exit(syncRes.status ?? 1);
}
const PACKS = ['native', 'core', 'product', 'engineering', 'vanilla'];
const REQUIRED = [
  'Agents/.gitkeep',
  'Files/AGENTS.md',
  'Files/.hermes.md',
  'Files/README.md',
  'SETUP.md',
  'README.md',
  'docker-compose.yml',
  '.env.example',
  '.env',
  'docs/PUBLIC_DEPLOY.md',
  'scripts/bootstrap-native.sh',
  'scripts/bootstrap-native.ps1',
  'scripts/bootstrap-profiles.sh',
  'scripts/bootstrap-profiles.ps1',
  'scripts/add-profile.sh',
  'scripts/add-profile.ps1',
  'scripts/open-setup.sh',
  'scripts/open-setup.ps1',
  'scripts/install.sh',
  'scripts/install.ps1',
  'scripts/start-install.sh',
  'scripts/start-install.ps1',
  'scripts/launch-install.ps1',
  'scripts/launch-install.sh',
  'scripts/open-chat.ps1',
  'scripts/open-chat.sh',
  'scripts/open-workframe-api.ps1',
  'scripts/open-workframe-api.sh',
  'scripts/open-workframe-ui.ps1',
  'scripts/open-workframe-ui.sh',
  'scripts/update-hermes.ps1',
  'scripts/update-hermes.sh',
  'scripts/setup-stack-secrets.sh',
  'scripts/agent-lifecycle.mjs',
  'scripts/lib/workframe-registry.mjs',
  'scripts/chat.sh',
  'scripts/chat.ps1',
  'scripts/verify-bootstrap.sh',
  'scripts/verify-bootstrap.ps1',
  'scripts/seed/agent-template/SOUL.md',
  'workframe-api/server.py',
  'workframe-api/public/index.html',
  'workframe-api/data/.gitkeep',
  'workframe-supervisor/server.py',
  'workframe-supervisor/Dockerfile',
  'workframe-ui/public/index.html',
  'workframe-ui/public/workframe-config.json',
  'workframe-ui/public/workframe-build.json',
  'workframe-ui/docker/nginx.conf',
  'docker/dashboard-proxy.conf',
  'workframe-manifest.json',
];

function slugify(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'workframe';
}

function nativeProfileSlug(name) {
  return `${slugify(name)}-agent`;
}

function nativeAgentName(name) {
  return `${name} Agent`;
}

function dockerStack(name) {
  return slugify(name);
}

/** WF-032: bootstrap invariants may live in extracted modules, not only server.py */
function readWorkframeApiSources(root) {
  const apiDir = path.join(root, 'workframe-api');
  const names = [
    'server.py',
    'chat_sessions.py',
    'lane_bindings.py',
    'profile_gateway.py',
    'turn_overlay.py',
    'credential_vault.py',
    'auth_gate.py',
    'internal_proxy_auth.py',
    'workspace_bootstrap.py',
  ];
  return names
    .map((name) => path.join(apiDir, name))
    .filter((fp) => fs.existsSync(fp))
    .map((fp) => fs.readFileSync(fp, 'utf8'))
    .join('\n');
}

function fail(msg) {
  console.error(`FAIL: ${msg}`);
  process.exit(1);
}

function assertFile(root, rel) {
  const file = path.join(root, rel);
  if (!fs.existsSync(file)) fail(`missing ${rel} in ${root}`);
}

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'wf-test-'));
console.log(`Scaffold test dir: ${tmp}`);

for (const pack of PACKS) {
  const name = `Test_${pack}`;
  const res = spawnSync(process.execPath, [CLI, name, '--pack', pack, '--out', tmp, '--ci', '--force'], {
    encoding: 'utf8',
  });
  if (res.status !== 0) fail(`pack ${pack}: ${res.stderr || res.stdout}`);
  const root = path.join(tmp, name);
  for (const rel of REQUIRED) assertFile(root, rel);

  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'workframe-manifest.json'), 'utf8'));
  const expectedSlug = nativeProfileSlug(name);
  const expectedName = nativeAgentName(name);
  const expectedStack = dockerStack(name);

  if (manifest.native_agent?.profile_slug !== expectedSlug) {
    fail(`pack ${pack}: expected native slug ${expectedSlug}, got ${manifest.native_agent?.profile_slug}`);
  }
  if (manifest.native_agent?.display_name !== expectedName) {
    fail(`pack ${pack}: expected native name ${expectedName}, got ${manifest.native_agent?.display_name}`);
  }
  if (!manifest.package_version) fail(`pack ${pack}: manifest missing package_version`);
  if (manifest.docker?.stack !== expectedStack) {
    fail(`pack ${pack}: expected docker stack ${expectedStack}, got ${manifest.docker?.stack}`);
  }
  if (manifest.docker?.containers?.gateway !== `${expectedStack}-gateway`) {
    fail(`pack ${pack}: unexpected gateway container name`);
  }
  if (manifest.docker?.containers?.workframe !== `${expectedStack}-workframe`) {
    fail(`pack ${pack}: unexpected workframe container name`);
  }
  if (manifest.docker?.containers?.workframe_api !== `${expectedStack}-workframe-api`) {
    fail(`pack ${pack}: unexpected workframe-api container name`);
  }
  if (!manifest.profiles.includes(expectedSlug)) {
    fail(`pack ${pack}: profiles missing native slug ${expectedSlug}`);
  }
  if (pack === 'native') {
    if (manifest.profiles.length !== 1 || manifest.profiles[0] !== expectedSlug) {
      fail(`pack ${pack}: expected native-only bootstrap profiles, got ${manifest.profiles.join(', ')}`);
    }
    if (manifest.profiles_installed_after_native_bootstrap?.length !== 1 || manifest.profiles_installed_after_native_bootstrap?.[0] !== expectedSlug) {
      fail(`pack ${pack}: expected native-only installed_after_native_bootstrap`);
    }
  }
  if (!manifest.profiles_catalog?.length) fail(`pack ${pack}: manifest missing profiles_catalog`);
  if (manifest.bootstrap?.default !== 'native') fail(`pack ${pack}: bootstrap.default should be native`);
  if (!manifest.ports?.gateway || !manifest.ports?.dashboard || !manifest.ports?.ui || !manifest.ports?.api) {
    fail(`pack ${pack}: manifest missing ports`);
  }
  if (manifest.layout?.workspace !== 'Files' || manifest.layout?.runtime !== 'Agents') {
    fail(`pack ${pack}: manifest layout should stay Files/Agents`);
  }

  assertFile(root, `scripts/seed/profiles/${expectedSlug}/SOUL.md`);
  assertFile(root, `scripts/seed/profiles/${expectedSlug}/SETUP.md`);

  const nativeSoul = fs.readFileSync(path.join(root, `scripts/seed/profiles/${expectedSlug}/SOUL.md`), 'utf8');
  if (!nativeSoul.includes('Setup gate')) fail(`pack ${pack}: native SOUL missing setup gate`);
  const nativeSetup = fs.readFileSync(path.join(root, `scripts/seed/profiles/${expectedSlug}/SETUP.md`), 'utf8');
  if (!nativeSetup.includes('Credential security')) fail(`pack ${pack}: native SETUP missing credential section`);

  const compose = fs.readFileSync(path.join(root, 'docker-compose.yml'), 'utf8');
  if (!compose.includes(`container_name: ${expectedStack}-gateway`)) {
    fail(`pack ${pack}: compose missing named gateway container`);
  }
  if (!compose.includes(`container_name: ${expectedStack}-workframe`)) {
    fail(`pack ${pack}: compose missing workframe UI container`);
  }
  if (!compose.includes(`container_name: ${expectedStack}-workframe-api`)) {
    fail(`pack ${pack}: compose missing workframe-api container`);
  }
  if (!compose.includes(`container_name: ${expectedStack}-workframe-supervisor`)) {
    fail(`pack ${pack}: compose missing workframe-supervisor container`);
  }
  if (!compose.includes('context: ./workframe-supervisor')) {
    fail(`pack ${pack}: compose missing workframe-supervisor build context`);
  }
  if (!compose.includes('WORKFRAME_SUPERVISOR_URL=http://workframe-supervisor:8090')) {
    fail(`pack ${pack}: compose missing supervisor URL for API`);
  }
  if (!compose.includes('internal: true')) {
    fail(`pack ${pack}: compose missing internal control network`);
  }
  const gatewayBlock = compose.split(/^  (?=[a-z])/m).find((block) => block.startsWith('gateway:'));
  if (gatewayBlock?.includes('env_file:')) {
    fail(`pack ${pack}: gateway must not use env_file (secrets stay off Hermes container)`);
  }
  if (!compose.includes('workframe-proxy-token:/run/workframe-proxy')) {
    fail(`pack ${pack}: compose missing shared proxy token volume`);
  }
  if (!compose.includes('WORKFRAME_PROXY_TOKEN')) {
    fail(`pack ${pack}: compose missing WORKFRAME_PROXY_TOKEN`);
  }
  if (!compose.includes('gateway run') || !compose.includes(`-p ${expectedSlug}`)) {
    fail(`pack ${pack}: compose gateway missing native profile ${expectedSlug}`);
  }
  if (!gatewayBlock?.includes('./Agents:/opt/data')) {
    fail(`pack ${pack}: gateway must mount ./Agents:/opt/data (not host Hermes)`);
  }
  if (gatewayBlock?.includes('AppData/Local/hermes') || gatewayBlock?.includes('/.hermes')) {
    fail(`pack ${pack}: gateway must not bind host Hermes into the stack`);
  }
  if (!compose.includes('./workframe-api/public:/app/public:ro')) {
    fail(`pack ${pack}: compose missing workframe-api public mount`);
  }
  if (!compose.includes('WORKFRAME_UI_STATIC_DIR:-./workframe-ui/public') && !compose.includes('./workframe-ui/public:/usr/share/nginx/html:ro')) {
    fail(`pack ${pack}: compose missing workframe-ui public mount`);
  }
  if (!compose.includes('./workframe-ui/docker/nginx.conf:/etc/nginx/conf.d/default.conf:ro')) {
    fail(`pack ${pack}: compose missing workframe-ui nginx mount`);
  }
  if (!compose.includes('./docker/dashboard-proxy.conf:/etc/nginx/conf.d/default.conf:ro')) {
    fail(`pack ${pack}: compose missing dashboard proxy mount`);
  }
  if (!compose.includes('./scripts:/opt/install/scripts:ro')) {
    fail(`pack ${pack}: docker-compose must mount scripts`);
  }
  if (!compose.includes('HERMES_DASHBOARD_TUI=1')) {
    fail(`pack ${pack}: compose missing dashboard TUI enablement`);
  }
  if (gatewayBlock?.includes('HERMES_DASHBOARD_INSECURE=1')) {
    fail(`pack ${pack}: gateway must use dashboard basic auth, not HERMES_DASHBOARD_INSECURE`);
  }
  if (!gatewayBlock?.includes('HERMES_DASHBOARD_BASIC_AUTH_USERNAME')) {
    fail(`pack ${pack}: gateway missing dashboard basic auth env`);
  }
  if (compose.includes('mission-control')) {
    fail(`pack ${pack}: compose should not include mission-control in the default stack`);
  }

  const publicCompose = fs.readFileSync(path.join(root, 'docker-compose.public.yml'), 'utf8');
  if (!fs.existsSync(path.join(root, 'docker-compose.host-bindings.yml'))) {
    fail(`pack ${pack}: missing docker-compose.host-bindings.yml for supervisor apply`);
  }
  const hostBindings = fs.readFileSync(path.join(root, 'docker-compose.host-bindings.yml'), 'utf8');
  if (!hostBindings.includes('WORKFRAME_HOST_PROJECT_ROOT')) {
    fail(`pack ${pack}: host-bindings overlay must use WORKFRAME_HOST_PROJECT_ROOT`);
  }
  if (!compose.includes('.:/project:ro') || !compose.includes('.:/compose:ro')) {
    fail(`pack ${pack}: API compose must mount the project root for manifest-backed updates`);
  }
  const publicApiBlock = publicCompose.split(/^  (?=[a-z])/m).find((block) => block.startsWith('workframe-api:'));
  if (publicApiBlock?.includes('/var/run/docker.sock')) {
    fail(`pack ${pack}: docker-compose.public.yml must not mount docker.sock on workframe-api`);
  }
  if (!publicCompose.includes('workframe-proxy-token:/run/workframe-proxy')) {
    fail(`pack ${pack}: docker-compose.public.yml missing proxy token volume on API`);
  }

  const envExample = fs.readFileSync(path.join(root, '.env.example'), 'utf8');
  if (!envExample.includes('WORKFRAME_PROXY_TOKEN')) {
    fail(`pack ${pack}: .env.example missing WORKFRAME_PROXY_TOKEN`);
  }
  if (!envExample.includes('WORKFRAME_VAULT_KEK')) {
    fail(`pack ${pack}: .env.example missing WORKFRAME_VAULT_KEK`);
  }

  const nginx = fs.readFileSync(path.join(root, 'workframe-ui/docker/nginx.conf'), 'utf8');
  if (nginx.includes('/hermes-profiles/')) {
    fail(`pack ${pack}: nginx should not include /hermes-profiles/ locations`);
  }

  const wfCfg = JSON.parse(fs.readFileSync(path.join(root, 'workframe-ui/public/workframe-config.json'), 'utf8'));
  if (wfCfg.native_profile !== expectedSlug) {
    fail(`pack ${pack}: workframe-config native_profile expected ${expectedSlug}, got ${wfCfg.native_profile}`);
  }
  if (wfCfg.project_name !== name) {
    fail(`pack ${pack}: workframe-config project_name expected ${name}, got ${wfCfg.project_name}`);
  }

  const pkgVersion = JSON.parse(fs.readFileSync(path.join(PKG_ROOT, 'package.json'), 'utf8')).version;
  const wfBuild = JSON.parse(fs.readFileSync(path.join(root, 'workframe-ui/public/workframe-build.json'), 'utf8'));
  if (wfBuild.package_version !== pkgVersion) {
    fail(`pack ${pack}: workframe-build package_version expected ${pkgVersion}, got ${wfBuild.package_version}`);
  }
  if (wfCfg.package_version !== pkgVersion) {
    fail(`pack ${pack}: workframe-config package_version expected ${pkgVersion}, got ${wfCfg.package_version}`);
  }

  const workspaceFiles = fs.readdirSync(path.join(root, 'Files')).sort();
  const expectedWorkspaceFiles = ['.hermes.md', 'AGENTS.md', 'README.md'];
  if (workspaceFiles.join('|') !== expectedWorkspaceFiles.join('|')) {
    fail(`pack ${pack}: Files/ should stay lean, got ${workspaceFiles.join(', ')}`);
  }

  const agents = fs.readFileSync(path.join(root, 'Files/AGENTS.md'), 'utf8');
  if (!agents.includes(expectedName)) fail(`pack ${pack}: AGENTS.md missing native agent name`);

  const readme = fs.readFileSync(path.join(root, 'README.md'), 'utf8');
  if (readme.includes('Workframe/scripts/')) fail(`pack ${pack}: README still references nested Workframe/scripts paths`);

  const setup = fs.readFileSync(path.join(root, 'SETUP.md'), 'utf8');
  if (!setup.includes('bootstrap-native')) fail(`pack ${pack}: SETUP.md missing native bootstrap`);
  if (!setup.includes('add-profile')) fail(`pack ${pack}: SETUP.md missing add-profile`);
  if (!setup.includes('start-install')) fail(`pack ${pack}: SETUP.md missing start-install`);
  if (setup.includes('mission control')) fail(`pack ${pack}: SETUP.md should not position mission control in the main flow`);

  const updateHermes = fs.readFileSync(path.join(root, 'scripts/update-hermes.ps1'), 'utf8');
  if (updateHermes.includes('dashboard-')) {
    fail(`pack ${pack}: update-hermes.ps1 should not recreate profile dashboard services`);
  }

  const chat = fs.readFileSync(path.join(root, 'scripts/chat.ps1'), 'utf8');
  if (!chat.includes(`-p ${expectedSlug}`)) fail(`pack ${pack}: chat.ps1 missing native profile flag`);
  if (!chat.includes(`${expectedStack}-chat`)) fail(`pack ${pack}: chat.ps1 missing named chat container`);

  const bootstrapNative = fs.readFileSync(path.join(root, 'scripts/bootstrap-native.ps1'), 'utf8');
  if (!bootstrapNative.includes(`profile use ${expectedSlug}`)) fail(`pack ${pack}: bootstrap-native missing profile use`);
  if (!bootstrapNative.includes('routes.json')) fail(`pack ${pack}: bootstrap-native must write Agents/workframe/routes.json`);
  if (!bootstrapNative.includes('SETUP.md')) fail(`pack ${pack}: bootstrap-native missing SETUP copy`);
  if (!bootstrapNative.includes('Agents\\SOUL.md')) fail(`pack ${pack}: bootstrap-native must install Agents/SOUL.md`);
  if (!bootstrapNative.includes('cwd: /workspace')) fail(`pack ${pack}: bootstrap-native must set terminal.cwd to /workspace`);

  const startInstall = fs.readFileSync(path.join(root, 'scripts/start-install.ps1'), 'utf8');
  if (!startInstall.includes('open-install-ui.ps1')) fail(`pack ${pack}: start-install.ps1 missing open-install-ui`);
  const startInstallSh = fs.readFileSync(path.join(root, 'scripts/start-install.sh'), 'utf8');
  if (!startInstallSh.includes('open-install-ui.sh')) fail(`pack ${pack}: start-install.sh missing open-install-ui`);
  if (!fs.existsSync(path.join(root, 'scripts/apply-update-hermes.sh'))) {
    fail(`pack ${pack}: missing scripts/apply-update-hermes.sh`);
  }
  if (!fs.existsSync(path.join(root, 'scripts/apply-update-workframe.sh'))) {
    fail(`pack ${pack}: missing scripts/apply-update-workframe.sh`);
  }
  const installPs1 = fs.readFileSync(path.join(root, 'scripts/install.ps1'), 'utf8');
  if (!installPs1.includes('open-workframe-ui.ps1')) fail(`pack ${pack}: install.ps1 missing open-workframe-ui`);
  const installSh = fs.readFileSync(path.join(root, 'scripts/install.sh'), 'utf8');
  if (!installSh.includes('open-workframe-ui.sh')) fail(`pack ${pack}: install.sh missing open-workframe-ui`);
  const launchSh = fs.readFileSync(path.join(root, 'scripts/launch-install.sh'), 'utf8');
  if (!launchSh.includes('start-install.sh')) fail(`pack ${pack}: launch-install.sh missing start-install`);

  const addProfile = fs.readFileSync(path.join(root, 'scripts/add-profile.ps1'), 'utf8');
  if (!addProfile.includes("'dev'")) fail(`pack ${pack}: add-profile missing dev in catalog`);

  const verify = fs.readFileSync(path.join(root, 'scripts/verify-bootstrap.ps1'), 'utf8');
  if (!verify.includes('bootstrap-native')) fail(`pack ${pack}: verify-bootstrap should mention bootstrap-native`);
  if (!verify.includes('Agents\\SOUL.md')) fail(`pack ${pack}: verify-bootstrap must check Agents\\SOUL.md`);

  const workframeApi = readWorkframeApiSources(root);
  if (!workframeApi.includes('active_id = persistent_id if persistent_valid else ""')) {
    fail(`pack ${pack}: workframe-api bootstrap should not treat latest native session as active`);
  }
  if (workframeApi.includes('latest = _latest_session_id(prof)')) {
    fail(`pack ${pack}: workframe-api should not fall back to latest session in profile_chat_session`);
  }
  if (!workframeApi.includes('binding_version = _binding_version(payload.get("binding_version"))')) {
    fail(`pack ${pack}: workframe-api should version native UI bindings`);
  }
  if (!workframeApi.includes('"binding_version": binding_version')) {
    fail(`pack ${pack}: workframe-api should persist binding_version in lane bindings`);
  }
  if (!workframeApi.includes('_wait_profile_api_healthy(profile: str, attempts: int = 60')) {
    fail(`pack ${pack}: workframe-api must wait >=30s for cold u-* profile health`);
  }
  if (!workframeApi.includes('http://gateway:')) {
    fail(`pack ${pack}: workframe-api profile health must probe gateway DNS from BFF container`);
  }
  if (!workframeApi.includes('for attempt in range(3)')) {
    fail(`pack ${pack}: bootstrap_agent_dm_lane must retry gateway start up to 3 times`);
  }

  if (!workframeApi.includes('internal_proxy_auth')) {
    fail(`pack ${pack}: workframe-api missing internal proxy auth`);
  }
  if (!workframeApi.includes('credential_vault.bootstrap_vault')) {
    fail(`pack ${pack}: workframe-api missing vault envelope bootstrap`);
  }
  if (!workframeApi.includes('_invite_only_login_enforced')) {
    fail(`pack ${pack}: workframe-api missing invite-only login gate`);
  }

  const supervisorPy = fs.readFileSync(path.join(root, 'workframe-supervisor/server.py'), 'utf8');
  if (!supervisorPy.includes('for _ in range(60):')) {
    fail(`pack ${pack}: workframe-supervisor must wait >=30s for profile gateway health`);
  }

  console.log(`OK pack=${pack} native=${expectedSlug} docker=${expectedStack}`);
}

const baRes = spawnSync(process.execPath, [CLI, 'BrandAuthority', '--pack', 'vanilla', '--out', tmp, '--ci', '--force'], {
  encoding: 'utf8',
});
if (baRes.status !== 0) fail(`BrandAuthority scaffold: ${baRes.stderr || baRes.stdout}`);
const baManifest = JSON.parse(fs.readFileSync(path.join(tmp, 'BrandAuthority', 'workframe-manifest.json'), 'utf8'));
if (baManifest.native_agent.profile_slug !== 'brandauthority-agent') {
  fail(`BrandAuthority slug expected brandauthority-agent, got ${baManifest.native_agent.profile_slug}`);
}
if (baManifest.docker.stack !== 'brandauthority') {
  fail(`BrandAuthority docker stack expected brandauthority`);
}
console.log('OK BrandAuthority -> brandauthority-agent / brandauthority stack');

for (const bad of ['.', '..', '../escape', 'bad/name']) {
  const res = spawnSync(process.execPath, [CLI, '--name', bad, '--out', tmp, '--ci', '--force'], { encoding: 'utf8' });
  if (res.status === 0) fail(`expected rejection for name=${bad}`);
}
console.log('OK rejected unsafe project names');

console.log('All scaffold tests passed.');
