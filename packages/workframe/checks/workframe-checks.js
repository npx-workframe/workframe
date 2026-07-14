import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import {
  createSessionSeed,
  interpretConsent,
  parseCliArgs,
  parsePreferredName,
  selectInferenceCandidate,
} from '../bin/workframe.js';

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const CLI = path.join(PACKAGE_ROOT, 'bin', 'workframe.js');

test('negative consent overrides positive words', () => {
  assert.equal(interpretConsent("Sure, but don't do it yet."), 'no');
  assert.equal(interpretConsent('yes, later'), 'no');
});

test('consent accepts explicit natural language and rejects ambiguity', () => {
  assert.equal(interpretConsent('Go ahead and test it, please.'), 'yes');
  assert.equal(interpretConsent('That sounds interesting.'), 'unknown');
});

test('preferred name accepts direct and conversational answers', () => {
  assert.equal(parsePreferredName('Alan'), 'Alan');
  assert.equal(parsePreferredName('Please call me Ada.'), 'Ada');
  assert.equal(parsePreferredName(''), 'human');
});

test('session seed is a bounded memory-only draft', () => {
  const seed = createSessionSeed({
    preferredName: 'Call me Alan',
    objective: 'Build a system that helps me define and deploy an entity.',
    candidate: { id: 'codex', label: 'Codex CLI' },
  });

  assert.deepEqual(seed, {
    status: 'draft',
    persistence: 'memory-only',
    human: { preferredName: 'Alan' },
    entity: {
      statedObjective: 'Build a system that helps me define and deploy an entity.',
      unresolved: ['purpose', 'constraints', 'success criteria'],
    },
    inference: { id: 'codex', label: 'Codex CLI', status: 'verified' },
  });
});

test('authenticated runtimes take precedence over configured API keys', () => {
  const candidate = selectInferenceCandidate({
    runtimes: [
      { id: 'codex', status: 'authenticated' },
      { id: 'claude', status: 'verified' },
    ],
    providers: [
      { id: 'openrouter', status: 'configured' },
      { id: 'openai', status: 'configured' },
    ],
  });

  assert.equal(candidate.id, 'codex');
});

test('flag-only version and help invocations are parsed correctly', () => {
  assert.equal(parseCliArgs(['--version']).command, 'version');
  assert.equal(parseCliArgs(['-h']).command, 'help');
  assert.equal(parseCliArgs(['begin']).command, 'begin');
});

test('CLI version emits only the semantic version', () => {
  const result = spawnSync(process.execPath, [CLI, '--version'], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout.trim(), /^\d+\.\d+\.\d+$/);
});

test('status JSON is valid and contains no credential values', () => {
  const secret = 'wf-test-secret-value';
  const result = spawnSync(process.execPath, [CLI, 'status', '--json'], {
    encoding: 'utf8',
    env: { ...process.env, OPENAI_API_KEY: secret },
  });

  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.providers.find((provider) => provider.id === 'openai').status, 'configured');
  assert.equal(result.stdout.includes(secret), false);
});
