import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildFormationPlan, chooseInferencePath, parseGoals } from '../bin/origin-start.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const fixture = {
  runtimes: [
    { id: 'codex', label: 'Codex CLI', status: 'authenticated' },
    { id: 'claude', label: 'Claude Code', status: 'verified' },
  ],
  providers: [],
};

assert.deepEqual(parseGoals('1,biz,project,1'), ['organization', 'business', 'project']);
assert.deepEqual(chooseInferencePath(fixture), { kind: 'runtime', id: 'codex', label: 'Codex CLI' });
const plan = buildFormationPlan(fixture, ['project']);
assert.equal(plan.mode, 'plan_only');
assert.equal(plan.authorization_required, true);
assert.deepEqual(plan.inspected_paths, []);
assert.deepEqual(plan.mutations, []);

const version = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8')).version;
const delegated = spawnSync(process.execPath, [path.join(root, 'bin/workframe-cli.js'), 'version'], { encoding: 'utf8' });
assert.equal(delegated.status, 0, delegated.stderr);
assert.equal(delegated.stdout.trim(), version);

const run = spawnSync(process.execPath, [
  path.join(root, 'bin/workframe-cli.js'),
  'start',
  '--json',
  '--goals=business,project',
], { encoding: 'utf8' });
assert.equal(run.status, 0, run.stderr);
const output = JSON.parse(run.stdout);
assert.deepEqual(output.goals, ['business', 'project']);
assert.equal(output.authorization_required, true);
assert.deepEqual(output.inspected_paths, []);
assert.deepEqual(output.mutations, []);

console.log('origin start checks passed');
