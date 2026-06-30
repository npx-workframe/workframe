#!/usr/bin/env node
/** Copy canonical preset PNGs + catalogs into dist for nginx /assets/* serve. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const assetRoot = path.join(root, 'src', 'assets');
const distRoot = path.join(root, 'dist', 'assets');

const presetDirs = ['avatars', 'project-logos', 'branding'];

for (const dir of presetDirs) {
  const src = path.join(assetRoot, dir);
  const dest = path.join(distRoot, dir);
  if (!fs.existsSync(src)) continue;
  fs.mkdirSync(dest, { recursive: true });
  for (const name of fs.readdirSync(src)) {
    const from = path.join(src, name);
    if (!fs.statSync(from).isFile()) continue;
    if (name.endsWith('.png') || name === 'catalog.json') {
      fs.copyFileSync(from, path.join(dest, name));
    }
  }
}
