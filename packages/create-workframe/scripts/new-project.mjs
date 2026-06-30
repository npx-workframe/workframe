#!/usr/bin/env node
/**
 * Canonical dev/test bootstrap: bundle UI (meta layout only) → scaffold → auto-launch Phase B.
 *
 * Meta repo:
 *   node packages/create-workframe/scripts/new-project.mjs BrandAuthority --out D:/Workframe --force
 *
 * Published npm (UI already bundled in package):
 *   npx create-workframe BrandAuthority --out D:/Workframe --force
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { spawnSync } from 'child_process';

const PKG_ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const CLI = path.join(PKG_ROOT, 'bin', 'create-workframe.js');
const BUNDLE = path.join(PKG_ROOT, 'scripts', 'bundle-workframe-ui.mjs');
const UI_SOURCE = path.join(PKG_ROOT, '..', 'workframe-ui', 'package.json');

function usage() {
  console.log(`new-project — scaffold + Phase B installer (Workframe UI bundled when developing from meta)

Usage:
  node scripts/new-project.mjs <ProjectName> [--out DIR] [--force] [--no-launch] [--no-bundle]

Examples:
  node scripts/new-project.mjs BrandAuthority --out D:/Workframe --force
  node scripts/new-project.mjs Demo --out /tmp/projects

Notes:
  - Auto-bundles Workframe UI when run from the meta repo (workframe-ui source present).
  - Skips bundle when installed from npm (pre-bundled UI in the package).
  - Phase B installer opens in a new terminal; complete Hermes setup there.
  - Equivalent published command: npx create-workframe <ProjectName> --out <DIR> --force
`);
}

const argv = process.argv.slice(2);
if (!argv.length || argv.includes('-h') || argv.includes('--help')) {
  usage();
  process.exit(argv.length ? 0 : 1);
}

const noBundle = argv.includes('--no-bundle');
const noLaunch = argv.includes('--no-launch');
const forwarded = argv.filter((a) => a !== '--no-bundle');

const isMetaDevLayout = fs.existsSync(UI_SOURCE);
if (isMetaDevLayout && !noBundle) {
  console.log('Bundling Workframe UI into create-workframe…');
  const bundle = spawnSync(process.execPath, [BUNDLE], {
    stdio: 'inherit',
    cwd: path.dirname(BUNDLE),
  });
  if (bundle.status !== 0) process.exit(bundle.status ?? 1);
} else if (!isMetaDevLayout && !noBundle) {
  console.log('Using pre-bundled Workframe UI from create-workframe package.');
}

const scaffold = spawnSync(process.execPath, [CLI, ...forwarded], { stdio: 'inherit' });
if (scaffold.status !== 0) process.exit(scaffold.status ?? 1);

if (!noLaunch) {
  console.log('');
  console.log('Next: complete Hermes setup in the Phase B installer window.');
  console.log('Re-open installer manually: .\\scripts\\start-install.ps1 or ./scripts/start-install.sh');
}
