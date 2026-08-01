#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const helperPath = path.join(root, 'scripts/workframe/compose-docker-host.sh');
const source = fs.readFileSync(helperPath, 'utf8');
const applyPath = path.join(root, 'scripts/workframe/apply-update-workframe.sh');
const applySource = fs.readFileSync(applyPath, 'utf8');
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
  !applySource.includes('-w "${host_cd}"'),
  'Deferred supervisor restart must never use a Windows host path as a container working directory.',
);

if (failures.length) {
  console.error('UPDATER CONTRACT VERIFY FAILED:');
  for (const failure of failures) console.error(`  - ${failure}`);
  process.exit(1);
}

console.log('OK: updater cleanup is bounded and cannot hold a completed update open.');
