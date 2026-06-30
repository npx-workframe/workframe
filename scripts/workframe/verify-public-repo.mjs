#!/usr/bin/env node
/**
 * Fail if tracked public repo contains private/operator patterns.
 * Cross-platform counterpart to verify-public-repo.ps1.
 */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '../..');

const patterns = [
  /[redacted]/i,
  /[redacted]/i,
  /click\.blue/i,
  /d:\\ab/i,
  /d:\/ab/i,
  /D:\\ab/i,
  /D:\/ab/i,
  /[redacted]/i,
  /[redacted]/i,
  /[redacted]/i,
  /architectonic\/workframe/i,
  /95\.216\.136/,
  /workframe\.io/i,
];

const forbiddenPaths = [
  'services/workframe-api/tests',
  'services/workframe-supervisor/tests',
  'apps/web/e2e',
  'packages/contracts',
  'packages/workframe-integrations',
  'docs/integrations',
];

const testPathPattern = /(^|\/)(tests|e2e)(\/|$)|\.test\.(ts|js)$|\.spec\.(ts|js)$/;
const selfName = 'scripts/workframe/verify-public-repo.mjs';
const selfNamePs1 = 'scripts/workframe/verify-public-repo.ps1';

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

for (const forbidden of forbiddenPaths) {
  const tracked = gitLsFiles(forbidden);
  if (tracked.length > 0) {
    console.error(`TRACKED FORBIDDEN PATH: ${forbidden}`);
    process.exit(1);
  }
}

const hits = [];
for (const rel of gitLsAllFiles()) {
  if (rel === selfName || rel === selfNamePs1) {
    continue;
  }
  if (testPathPattern.test(rel)) {
    hits.push(`forbidden path: ${rel}`);
    continue;
  }

  const full = path.join(root, rel);
  if (!fs.existsSync(full) || !fs.statSync(full).isFile()) {
    continue;
  }

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

console.log('OK: public repo verify passed');
