#!/usr/bin/env node
/**
 * Set stack_config.install_complete when workframe.db already has users (production recovery only).
 * Do not use for E2E — use reset-dogfood-docker.ps1 or wipe VPS runtime for a clean install test.
 * Usage: node repair-install-complete.mjs [--data-dir path]
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '../..');
const dataDir = process.argv.includes('--data-dir')
  ? process.argv[process.argv.indexOf('--data-dir') + 1]
  : path.join(root, 'runtime/workframe-api-data');
const stackPath = path.join(dataDir, 'stack_config.json');
const dbPath = path.join(dataDir, 'workframe.db');

if (!fs.existsSync(stackPath)) {
  console.error(`Missing ${stackPath}`);
  process.exit(1);
}
if (!fs.existsSync(dbPath)) {
  console.error(`Missing ${dbPath}`);
  process.exit(1);
}

// ponytail: sqlite via python — no native dep in node script
import { spawnSync } from 'node:child_process';
const countProc = spawnSync(
  'python3',
  [
    '-c',
    `import sqlite3; print(sqlite3.connect(${JSON.stringify(dbPath)}).execute('select count(*) from users').fetchone()[0])`,
  ],
  { encoding: 'utf8' },
);
if (countProc.status !== 0) {
  console.error(countProc.stderr || 'sqlite count failed');
  process.exit(1);
}
const users = Number(String(countProc.stdout).trim() || '0');
const stack = JSON.parse(fs.readFileSync(stackPath, 'utf8'));
if (users > 0) {
  stack.install_complete = true;
  fs.writeFileSync(stackPath, `${JSON.stringify(stack, null, 2)}\n`);
}
console.log(JSON.stringify({ ok: true, users, install_complete: Boolean(stack.install_complete) }, null, 2));
