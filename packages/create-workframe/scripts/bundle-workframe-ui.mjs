#!/usr/bin/env node
/**
 * Build apps/web and copy dist into create-workframe/workframe-ui/public for npm publish.
 * Canonical UI pipeline: apps/web `npm run build` → dist (same as monorepo `pnpm build:web`).
 * Run from repository root: node packages/create-workframe/scripts/bundle-workframe-ui.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PKG_ROOT = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(PKG_ROOT, '../..');
const UI_SRC = path.join(REPO_ROOT, 'apps/web');
const UI_DEST = path.join(PKG_ROOT, 'workframe-ui', 'public');

function npmCmd() {
  return process.platform === 'win32' ? 'npm.cmd' : 'npm';
}

function copyTree(src, dst) {
  if (!fs.existsSync(src)) throw new Error(`Missing source: ${src}`);
  fs.rmSync(dst, { recursive: true, force: true });
  fs.mkdirSync(dst, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const from = path.join(src, entry.name);
    const to = path.join(dst, entry.name);
    if (entry.isDirectory()) copyTree(from, to);
    else fs.copyFileSync(from, to);
  }
}

const skipBuild = process.argv.includes('--skip-build');

if (!fs.existsSync(UI_SRC)) {
  console.error(`apps/web source not found: ${UI_SRC}`);
  process.exit(1);
}

if (!skipBuild) {
  console.log('Building @workframe/web...');
  const build = spawnSync(npmCmd(), ['run', 'build'], {
    cwd: UI_SRC,
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });
  if (build.status !== 0) process.exit(build.status ?? 1);
} else {
  console.log('Skipping @workframe/web build (--skip-build)');
}

const dist = path.join(UI_SRC, 'dist');
if (!fs.existsSync(path.join(dist, 'index.html'))) {
  console.error(`Build output missing index.html in ${dist}`);
  process.exit(1);
}

console.log(`Copying ${dist} -> ${UI_DEST}`);
copyTree(dist, UI_DEST);

const pkgVersion = JSON.parse(fs.readFileSync(path.join(PKG_ROOT, 'package.json'), 'utf8')).version;
const gitRef = spawnSync('git', ['rev-parse', '--short', 'HEAD'], { encoding: 'utf8', cwd: REPO_ROOT });
const buildStamp = {
  package_version: pkgVersion,
  bundled_at: new Date().toISOString(),
  git_ref: gitRef.status === 0 ? gitRef.stdout.trim() : '',
};
fs.writeFileSync(path.join(UI_DEST, 'workframe-build.json'), `${JSON.stringify(buildStamp, null, 2)}\n`);

const avatarShared = path.join(PKG_ROOT, 'shared', 'agent-avatars');

function copyPresetPngs(src, dst, { keepCatalog = false } = {}) {
  if (!fs.existsSync(src)) return;
  fs.mkdirSync(dst, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (!entry.isFile() || !entry.name.endsWith('.png')) continue;
    fs.copyFileSync(path.join(src, entry.name), path.join(dst, entry.name));
  }
  if (keepCatalog && fs.existsSync(path.join(src, 'catalog.json'))) {
    fs.copyFileSync(path.join(src, 'catalog.json'), path.join(dst, 'catalog.json'));
  }
}

for (const dir of ['avatars', 'logos']) {
  copyPresetPngs(path.join(dist, 'assets', dir), path.join(UI_DEST, 'assets', dir), { keepCatalog: true });
}

// ponytail: shared/agent-avatars is npm-pack mirror of avatars only (legacy seed path)
copyPresetPngs(path.join(dist, 'assets', 'avatars'), avatarShared, { keepCatalog: true });

console.log('Workframe UI bundle ready for create-workframe.');
