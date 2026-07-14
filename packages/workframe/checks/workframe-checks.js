import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import {
  interpretCandidateChoice,
  interpretConsent,
  normalizeAnswer,
} from '../lib/dialogue.js';
import {
  createSessionSeed,
  parsePreferredName,
} from '../lib/session.js';

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const CLI = path.join(PACKAGE_ROOT, 'bin', 'workframe.js');
const candidates = [
  { id: 'codex', label: 'Codex CLI', aliases: ['codex'] },
  { id: 'claude', label: 'Claude Code', aliases: ['claude'] },
  { id: 'openrouter', label: 'OpenRouter', aliases: ['open router'] },
];

test('normalizeAnswer removes accents and punctuation without inventing intent', () => {
  assert.equal(normalizeAnswer('  Cláude, please!  '), 'claude please');
});

test('negative consent overrides positive language', () => {
  assert.equal(interpretConsent("Sure, but don't do it yet."), 'no');
  assert.equal(interpretConsent('Yes, not now.'), 'no');
});

test('consent accepts natural affirmative and preserves ambiguity', () => {
  assert.equal(interpretConsent('Sounds good, proceed.'), 'yes');
  assert.equal(interpretConsent('Tell me more first.'), 'unknown');
});

test('candidate choice resolves one explicit natural-language mention', () => {
  const result = interpretCandidateChoice('Use Claude Code for this.', candidates);
  assert.equal(result.kind, 'selected');
  assert.equal(result.candidate.id, 'claude');
});

test('candidate choice refuses to guess between multiple paths', () => {
  const result = interpretCandidateChoice('Codex or Claude would both be fine.', candidates);
  assert.equal(result.kind, 'ambiguous');
  assert.deepEqual(result.candidates.map((candidate) => candidate.id), ['codex', 'claude']);
});

test('candidate choice honors exclusions', () => {
  const result = interpretCandidateChoice('Anything except Claude or OpenRouter.', candidates);
  assert.equal(result.kind, 'selected');
  assert.equal(result.candidate.id, 'codex');
});

test('candidate choice uses deterministic order only when delegated', () => {
  const result = interpretCandidateChoice('Use whichever you recommend.', candidates);
  assert.equal(result.kind, 'selected');
  assert.equal(result.candidate.id, 'codex');
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

test('package bin emits only the semantic version', () => {
  const result = spawnSync(process.execPath, [CLI, '--version'], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout.trim(), /^\d+\.\d+\.\d+$/);
});

test('package bin runs through a POSIX symlink', { skip: process.platform === 'win32' }, () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'workframe-bin-'));
  const linkedCli = path.join(directory, 'workframe');
  try {
    fs.symlinkSync(CLI, linkedCli);
    const result = spawnSync(process.execPath, [linkedCli, '--version'], { encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout.trim(), /^\d+\.\d+\.\d+$/);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
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
