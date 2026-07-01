#!/usr/bin/env node
/**
 * Fail if tracked public repo contains private paths or operator-defined patterns.
 * Operator patterns live in verify-public-patterns.local.json (gitignored) — never in this file.
 */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '../..');
const localPatternsPath = path.join(__dirname, 'verify-public-patterns.local.json');
const strict = process.env.VERIFY_PUBLIC_STRICT === '1';

const forbiddenPaths = [
  'services/workframe-api/tests',
  'services/workframe-supervisor/tests',
  'apps/web/e2e',
  'packages/contracts',
  'packages/workframe-integrations',
  'docs/integrations',
];

const skipScan = new Set([
  'scripts/workframe/verify-public-patterns.local.json',
  'scripts/workframe/verify-public-patterns.example.json',
]);

const testPathPattern = /(^|\/)(tests|e2e)(\/|$)|\.test\.(ts|js)$|\.spec\.(ts|js)$/;

function gitLsFiles(target) {
  try {
    return execFileSync('git', ['-C', root, 'ls-files', '--', target], {
      encoding: 'utf8',
    })
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean);
  } catch {
    return [];
  }
}

function gitLsAllFiles() {
  return execFileSync('git', ['-C', root, 'ls-files'], { encoding: 'utf8' })
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

function loadOperatorPatterns() {
  if (!fs.existsSync(localPatternsPath)) {
    if (strict) {
      console.error(
        'PUBLIC REPO VERIFY FAILED: missing scripts/workframe/verify-public-patterns.local.json',
      );
      console.error('  Copy verify-public-patterns.example.json → verify-public-patterns.local.json');
      console.error('  and fill in your operator denylist (local file is gitignored).');
      process.exit(1);
    }
    return [];
  }
  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(localPatternsPath, 'utf8'));
  } catch (err) {
    console.error(`PUBLIC REPO VERIFY FAILED: invalid ${localPatternsPath}: ${err.message}`);
    process.exit(1);
  }
  const rows = Array.isArray(parsed?.patterns) ? parsed.patterns : [];
  return rows
    .map((row) => String(row ?? '').trim())
    .filter(Boolean)
    .map((literal) => new RegExp(literal.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i'));
}

for (const forbidden of forbiddenPaths) {
  const tracked = gitLsFiles(forbidden);
  if (tracked.length > 0) {
    console.error(`TRACKED FORBIDDEN PATH: ${forbidden}`);
    process.exit(1);
  }
}

const patterns = loadOperatorPatterns();
const hits = [];

for (const rel of gitLsAllFiles()) {
  if (skipScan.has(rel)) continue;
  if (testPathPattern.test(rel)) {
    hits.push(`forbidden path: ${rel}`);
    continue;
  }
  if (!patterns.length) continue;

  const full = path.join(root, rel);
  if (!fs.existsSync(full) || !fs.statSync(full).isFile()) continue;

  let text;
  try {
    text = fs.readFileSync(full, 'utf8');
  } catch {
    continue;
  }

  for (const pattern of patterns) {
    if (pattern.test(text)) {
      hits.push(`${rel} :: ${pattern}`);
      break;
    }
  }
}

if (hits.length > 0) {
  console.error('PUBLIC REPO VERIFY FAILED:');
  for (const hit of hits.slice(0, 50)) {
    console.error(`  ${hit}`);
  }
  process.exit(1);
}

if (patterns.length) {
  console.log(`OK: public repo verify passed (${patterns.length} operator patterns)`);
} else {
  console.log('OK: public repo verify passed (structural checks only; no local patterns file)');
}
