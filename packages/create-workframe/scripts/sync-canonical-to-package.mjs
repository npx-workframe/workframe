#!/usr/bin/env node
/**
 * Copy canonical Workframe BFF into create-workframe package tree before npm pack.
 * Run from repository root: node packages/create-workframe/scripts/sync-canonical-to-package.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PKG_ROOT = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(PKG_ROOT, '../..');
const CANONICAL_API = path.join(REPO_ROOT, 'services/workframe-api');
const PKG_API = path.join(PKG_ROOT, 'workframe-api');
const CANONICAL_SUPERVISOR = path.join(REPO_ROOT, 'services/workframe-supervisor');
const PKG_SUPERVISOR = path.join(PKG_ROOT, 'workframe-supervisor');

const SKIP_DIRS = new Set([
  'data',
  'tests',
  '__pycache__',
  '.pytest_cache',
  '.venv',
  'node_modules',
]);

const SKIP_FILES = new Set([
  'board.db',
  'workframe.db',
  'auth.db',
  'fix_crlf.py',
  'insert_endpoints.py',
]);

function shouldSkip(name, isDir) {
  if (SKIP_DIRS.has(name)) return true;
  if (!isDir && SKIP_FILES.has(name)) return true;
  if (!isDir && name.endsWith('.pyc')) return true;
  return false;
}

function copyTree(src, dst) {
  if (!fs.existsSync(src)) throw new Error(`Missing canonical source: ${src}`);
  fs.rmSync(dst, { recursive: true, force: true });
  fs.mkdirSync(dst, { recursive: true });

  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (shouldSkip(entry.name, entry.isDirectory())) continue;
    const from = path.join(src, entry.name);
    const to = path.join(dst, entry.name);
    if (entry.isDirectory()) copyTree(from, to);
    else fs.copyFileSync(from, to);
  }
}

function removeIfExists(p) {
  if (fs.existsSync(p)) fs.rmSync(p, { recursive: true, force: true });
}

/** Alpine sh breaks on CRLF (then\r). Normalize at pack time — Windows checkout is CRLF. */
function copyIntoPackage(src, dst) {
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  if (dst.endsWith('.sh')) {
    const text = fs.readFileSync(src, 'utf8').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    fs.writeFileSync(dst, text, 'utf8');
  } else {
    fs.copyFileSync(src, dst);
  }
}

console.log(`Sync canonical BFF: ${CANONICAL_API} -> ${PKG_API}`);
copyTree(CANONICAL_API, PKG_API);

console.log(`Sync canonical supervisor: ${CANONICAL_SUPERVISOR} -> ${PKG_SUPERVISOR}`);
copyTree(CANONICAL_SUPERVISOR, PKG_SUPERVISOR);

const dataDir = path.join(PKG_API, 'data');
fs.mkdirSync(dataDir, { recursive: true });
const gitkeep = path.join(dataDir, '.gitkeep');
if (!fs.existsSync(gitkeep)) fs.writeFileSync(gitkeep, '');

const catalogSrc = path.join(CANONICAL_API, 'data', 'avatar-catalog.json');
const catalogDst = path.join(PKG_API, 'data', 'avatar-catalog.json');
if (fs.existsSync(catalogSrc)) {
  fs.mkdirSync(path.dirname(catalogDst), { recursive: true });
  fs.copyFileSync(catalogSrc, catalogDst);
}
for (const name of ['user-avatar-catalog.json', 'logo-catalog.json']) {
  const src = path.join(CANONICAL_API, 'data', name);
  const dst = path.join(PKG_API, 'data', name);
  if (fs.existsSync(src)) {
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(src, dst);
  }
}

const missionControl = path.join(PKG_ROOT, 'mission-control');
removeIfExists(missionControl);
console.log('Removed deprecated mission-control from package tree');

const uiSrcMirror = path.join(PKG_ROOT, 'workframe-ui', 'src');
removeIfExists(uiSrcMirror);
console.log('Removed stale workframe-ui/src mirror (canonical UI is apps/web)');

const applyScripts = [
  'apply-update-hermes.sh',
  'apply-update-workframe.sh',
  'restart-gateway-hermes.sh',
  'compose-docker-host.sh',
  'setup-stack-secrets.sh',
  'bootstrap-workspace-link.sh',
  'verify-public-deploy.sh',
  'fix-zk-encryption-key.sh',
  'set-compose-public-url.mjs',
  'ensure-compose-host-paths.mjs',
];
for (const name of applyScripts) {
  const src = path.join(REPO_ROOT, 'scripts/workframe', name);
  const dst = path.join(PKG_ROOT, 'scripts', name);
  if (!fs.existsSync(src)) throw new Error(`Missing apply script: ${src}`);
  copyIntoPackage(src, dst);
  console.log(`Synced ${name} -> package/scripts/`);
}

for (const sh of fs.readdirSync(path.join(PKG_ROOT, 'scripts')).filter((n) => n.endsWith('.sh'))) {
  const p = path.join(PKG_ROOT, 'scripts', sh);
  if (fs.readFileSync(p).includes(0x0d)) {
    throw new Error(`CRLF remains in package script after sync: ${sh}`);
  }
}

const publicDeploySrc = path.join(REPO_ROOT, 'infra/compose/workframe/PUBLIC_DEPLOY.md');
const publicDeployDst = path.join(PKG_ROOT, 'docs/PUBLIC_DEPLOY.md');
if (fs.existsSync(publicDeploySrc)) {
  fs.mkdirSync(path.dirname(publicDeployDst), { recursive: true });
  fs.copyFileSync(publicDeploySrc, publicDeployDst);
  console.log('Synced PUBLIC_DEPLOY.md -> package/docs/');
}

const securityPublicSrc = path.join(REPO_ROOT, 'docs/public/security.md');
const securityPkgDst = path.join(PKG_ROOT, 'docs/security.md');
if (fs.existsSync(securityPublicSrc)) {
  fs.mkdirSync(path.dirname(securityPkgDst), { recursive: true });
  fs.copyFileSync(securityPublicSrc, securityPkgDst);
  console.log('Synced docs/public/security.md -> package/docs/security.md');
}

for (const name of ['LICENSE', 'NOTICE', 'SECURITY.md']) {
  const src = path.join(REPO_ROOT, name);
  const dst = path.join(PKG_ROOT, name);
  if (!fs.existsSync(src)) throw new Error(`Missing publish file: ${src}`);
  fs.copyFileSync(src, dst);
  console.log(`Synced ${name} -> package/`);
}

const uiStale = [
  'components.json',
  'eslint.config.js',
  'index.html',
  'package.json',
  'README.md',
  'tsconfig.app.json',
  'tsconfig.json',
  'tsconfig.node.json',
  'vite.config.ts',
  'scripts',
];
for (const name of uiStale) {
  removeIfExists(path.join(PKG_ROOT, 'workframe-ui', name));
}

console.log('Canonical sync complete. Run bundle-workframe-ui.mjs next.');
