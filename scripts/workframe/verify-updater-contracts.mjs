#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const helperPath = path.join(root, 'scripts/workframe/compose-docker-host.sh');
const source = fs.readFileSync(helperPath, 'utf8');
const applyPath = path.join(root, 'scripts/workframe/apply-update-workframe.sh');
const applySource = fs.readFileSync(applyPath, 'utf8');
const supervisorPath = path.join(root, 'services/workframe-supervisor/server.py');
const supervisorSource = fs.readFileSync(supervisorPath, 'utf8');
const generatorSource = fs.readFileSync(
  path.join(root, 'packages/create-workframe/bin/create-workframe.js'),
  'utf8',
);
const syncSource = fs.readFileSync(
  path.join(root, 'packages/create-workframe/scripts/sync-canonical-to-package.mjs'),
  'utf8',
);
const bundleSource = fs.readFileSync(
  path.join(root, 'packages/create-workframe/scripts/bundle-workframe-ui.mjs'),
  'utf8',
);
const canonicalNginx = fs.readFileSync(path.join(root, 'apps/web/docker/nginx.conf'), 'utf8');
const packageNginx = fs.readFileSync(
  path.join(root, 'packages/create-workframe/workframe-ui/docker/nginx.conf'),
  'utf8',
);
const sourceHostBindings = fs.readFileSync(
  path.join(root, 'infra/compose/workframe/docker-compose.host-bindings.yml'),
  'utf8',
);
const failures = [];

function requireContract(condition, message) {
  if (!condition) failures.push(message);
}

requireContract(
  source.includes('_wf_bounded_docker_cleanup()'),
  'Updater Docker cleanup must use a bounded helper.',
);
requireContract(
  source.includes('timeout -k 5 "$seconds" "$@"'),
  'Updater Docker cleanup must have a hard timeout and kill grace period.',
);

for (const line of source.split(/\r?\n/)) {
  const trimmed = line.trim();
  if (/^docker (?:container|image) prune\b/.test(trimmed)) {
    failures.push(`Unbounded Docker cleanup command: ${trimmed}`);
  }
}

requireContract(
  source.includes('_wf_bounded_docker_cleanup "dangling-image cleanup" docker image prune -f'),
  'Dangling-image cleanup must be bounded and non-fatal.',
);
requireContract(
  applySource.includes('local sibling_cd="/workframe-host"'),
  'Deferred supervisor restart must use a container-native working directory.',
);
requireContract(
  applySource.includes('-v "${host_cd}:${sibling_cd}"') && applySource.includes('-w "${sibling_cd}"'),
  'Deferred supervisor restart must mount the host install at its container-native working directory.',
);
requireContract(
  applySource.includes('local host_root="${WORKFRAME_HOST_PROJECT_ROOT:-$host_cd}"'),
  'Deferred supervisor restart must preserve the API-resolved host project root.',
);
requireContract(
  applySource.includes('-e "WORKFRAME_HOST_COMPOSE_DIR=${host_cd}"')
    && applySource.includes('-e "WORKFRAME_HOST_PROJECT_ROOT=${host_root}"'),
  'Deferred supervisor restart must override stale .env host paths with the resolved install paths.',
);
requireContract(
  applySource.includes('source: "${host_scripts_yaml}"')
    && applySource.includes('target: /opt/install/scripts')
    && applySource.includes('compose_cmd+=" -f .workframe-supervisor-restart.yml"'),
  'Deferred supervisor restart must override relative script binds with the resolved host script directory.',
);
requireContract(
  applySource.includes('docker exec \\"\\$supervisor_id\\" test -f /opt/install/scripts/apply-update-workframe.sh')
    && applySource.includes('docker exec \\"\\$supervisor_id\\" test -f /opt/install/scripts/apply-update-hermes.sh'),
  'Deferred supervisor restart must verify both updater scripts in the recreated container.',
);
requireContract(
  !applySource.includes('-w "${host_cd}"'),
  'Deferred supervisor restart must never use a Windows host path as a container working directory.',
);
requireContract(
  supervisorSource.includes('def _update_script(name: str) -> Path | None:')
    && supervisorSource.includes('COMPOSE_DIR / "scripts" / name')
    && supervisorSource.includes('COMPOSE_DIR / "scripts" / "workframe" / name'),
  'Supervisor must recover updater scripts from canonical install layouts when its script bind drifts.',
);
requireContract(
  generatorSource.includes('- \\${WORKFRAME_HOST_PROJECT_ROOT}/scripts:/opt/install/scripts:ro'),
  'Generated host-bindings overlay must pin the supervisor script mount to the absolute install root.',
);
requireContract(
  sourceHostBindings.includes('- ${WORKFRAME_HOST_PROJECT_ROOT}/scripts/workframe:/opt/install/scripts:ro'),
  'Source host-bindings overlay must pin the supervisor script mount to the absolute source root.',
);
requireContract(
  applySource.includes('WF_UPDATE_NGINX_SRC="$pkg/workframe-ui/docker/nginx.conf"')
    && applySource.includes('Syncing workframe-ui/docker/nginx.conf -> $nginx_conf')
    && applySource.includes('mv -f "$nginx_tmp" "$nginx_conf"'),
  'Workframe updates must sync the packaged nginx config before recreating the UI.',
);
requireContract(
  generatorSource.includes("path.join(PKG_ROOT, 'workframe-ui', 'docker', 'nginx.conf')")
    && generatorSource.includes("return fs.readFileSync(nginxPath, 'utf8')"),
  'Generated installs must consume the packaged canonical nginx config instead of a duplicate template.',
);
requireContract(
  syncSource.includes("path.join(REPO_ROOT, 'apps/web/docker/nginx.conf')")
    && syncSource.includes('copyIntoPackage(CANONICAL_UI_NGINX, PKG_UI_NGINX)'),
  'Canonical sync must copy the source UI nginx config into the installer package.',
);
requireContract(
  canonicalNginx === packageNginx,
  'Canonical and packaged UI nginx configs must be byte-identical.',
);
requireContract(
  canonicalNginx.includes('location = /index.html')
    && canonicalNginx.includes('Cache-Control "no-cache, no-store, must-revalidate" always'),
  'Canonical UI nginx must prevent index HTML caching across in-app updates.',
);
requireContract(
  bundleSource.includes('assertEntryAssetClosure')
    && bundleSource.includes("(?:\\.\\/|\\/)assets\\/")
    && bundleSource.includes('Bundled UI index references missing assets'),
  'UI bundling must cache-bust relative and absolute entry assets and reject missing files.',
);
requireContract(
  applySource.includes('_wf_validate_ui_tree')
    && applySource.includes('UI update staged and entry assets verified'),
  'In-app Workframe updates must validate a staged UI tree before replacing the live tree.',
);

if (failures.length) {
  console.error('UPDATER CONTRACT VERIFY FAILED:');
  for (const failure of failures) console.error(`  - ${failure}`);
  process.exit(1);
}

console.log('OK: updater cleanup is bounded and cannot hold a completed update open.');
