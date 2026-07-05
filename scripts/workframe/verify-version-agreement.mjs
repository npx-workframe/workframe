#!/usr/bin/env node
/**
 * Fail when public install copy disagrees with package metadata.
 * ponytail: single canonical version from create-workframe package.json
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '../..');

function readJson(rel) {
  return JSON.parse(readFileSync(join(root, rel), 'utf8'));
}

function readText(rel) {
  return readFileSync(join(root, rel), 'utf8');
}

const canonical = readJson('packages/create-workframe/package.json').version;
const rootVer = readJson('package.json').version;
const errors = [];

if (rootVer !== canonical) {
  errors.push(`package.json version ${rootVer} !== create-workframe ${canonical}`);
}

const pinned = `create-workframe@${canonical}`;
const files = [
  'README.md',
  'packages/create-workframe/README.md',
  'docs/public/install.md',
  'docs/public/what-is-workframe.md',
  'docs/VERSION.md',
];

for (const rel of files) {
  const text = readText(rel);
  const pin = text.match(/create-workframe@\d+\.\d+\.\d+/g) || [];
  const bad = pin.filter((p) => p !== pinned);
  if (bad.length) {
    errors.push(`${rel}: expected only ${pinned}, found ${[...new Set(bad)].join(', ')}`);
  }
  if (!text.includes(pinned)) {
    errors.push(`${rel}: missing ${pinned}`);
  }
}

const versionTable = readText('docs/VERSION.md');
const rowRe = new RegExp(`\\|\\s*create-workframe\\s*\\|\\s*${canonical.replace(/\./g, '\\.')}\\s*\\|`);
if (!rowRe.test(versionTable)) {
  errors.push(`docs/VERSION.md: create-workframe row must be ${canonical}`);
}

if (errors.length) {
  console.error('verify-version-agreement: FAIL');
  for (const e of errors) console.error(`  - ${e}`);
  process.exit(1);
}

console.log(`verify-version-agreement: OK (${canonical})`);
