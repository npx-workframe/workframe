#!/usr/bin/env node
/** Regenerate preset catalogs from PNGs, then sync apps/web/src/assets → workframe-api/catalog. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const assets = path.join(webRoot, 'src', 'assets');
const apiCatalog = path.resolve(webRoot, '../../services/workframe-api/catalog');

function labelFromStem(stem) {
  return stem.charAt(0).toUpperCase() + stem.slice(1);
}

function pngFiles(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((name) => name.endsWith('.png'))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));
}

function writeAvatarCatalog(dir) {
  const avatars = pngFiles(dir).map((file) => {
    const id = file.replace(/\.png$/i, '');
    return { id, file, label: labelFromStem(id) };
  });
  const catalog = {
    version: 3,
    public_base: '/assets/avatars',
    avatars,
  };
  fs.writeFileSync(path.join(dir, 'catalog.json'), `${JSON.stringify(catalog, null, 2)}\n`);
  return catalog;
}

function writeLogoCatalog(dir) {
  const logos = pngFiles(dir).map((file) => {
    const id = file.replace(/\.png$/i, '');
    return { id, file, label: `Logo ${id}` };
  });
  const catalog = {
    version: 2,
    public_base: '/assets/project-logos',
    logos,
  };
  fs.writeFileSync(path.join(dir, 'catalog.json'), `${JSON.stringify(catalog, null, 2)}\n`);
  return catalog;
}

fs.mkdirSync(apiCatalog, { recursive: true });

const avatarCatalogPath = path.join(assets, 'avatars', 'catalog.json');
writeAvatarCatalog(path.join(assets, 'avatars'));
writeLogoCatalog(path.join(assets, 'project-logos'));

const pairs = [
  [avatarCatalogPath, path.join(apiCatalog, 'avatar-catalog.json')],
  [avatarCatalogPath, path.join(apiCatalog, 'user-avatar-catalog.json')],
  [path.join(assets, 'project-logos', 'catalog.json'), path.join(apiCatalog, 'logo-catalog.json')],
];

for (const [src, dst] of pairs) {
  if (!fs.existsSync(src)) {
    console.warn(`skip missing catalog: ${src}`);
    continue;
  }
  fs.copyFileSync(src, dst);
  console.log(`${path.basename(path.dirname(src))}/${path.basename(src)} → ${path.relative(path.resolve(webRoot, '../..'), dst)}`);
}
