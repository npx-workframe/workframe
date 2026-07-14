import assert from 'node:assert/strict';
import test from 'node:test';

import {
  interpretCandidateChoice,
  interpretConsent,
  normalizeAnswer,
} from '../lib/dialogue.js';

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
  assert.equal(interpretConsent('Please explain the cost first.'), 'unknown');
  assert.equal(interpretConsent('Why not explain what will happen?'), 'unknown');
});

test('candidate choice resolves a single natural-language mention', () => {
  const result = interpretCandidateChoice('Use Claude Code for this.', candidates);
  assert.equal(result.kind, 'selected');
  assert.equal(result.candidate.id, 'claude');
});

test('candidate choice refuses to guess when multiple candidates are named', () => {
  const result = interpretCandidateChoice('Codex or Claude would both be fine.', candidates);
  assert.equal(result.kind, 'ambiguous');
  assert.deepEqual(result.candidates.map((candidate) => candidate.id), ['codex', 'claude']);
});

test('candidate choice honors exclusions', () => {
  const result = interpretCandidateChoice('Anything except Claude or OpenRouter.', candidates);
  assert.equal(result.kind, 'selected');
  assert.equal(result.candidate.id, 'codex');
});

test('candidate choice uses deterministic order only when delegated explicitly', () => {
  const result = interpretCandidateChoice('Use whichever you recommend.', candidates);
  assert.equal(result.kind, 'selected');
  assert.equal(result.candidate.id, 'codex');
});
