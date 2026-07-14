import assert from 'node:assert/strict';
import test from 'node:test';

import { interpretCandidateChoice, interpretConsent, normalizeAnswer } from '../lib/dialogue.js';
import { InputEndedError, runInteractiveFlow } from '../lib/flow.js';
import { createSessionSeed, parsePreferredName } from '../lib/session.js';

const candidates = [
  { id: 'codex-account', label: 'Codex CLI account', aliases: ['codex'], billingSource: 'Codex account', credentialSource: 'session', invocation: 'CLI' },
  { id: 'claude-account', label: 'Claude Code account', aliases: ['claude'], billingSource: 'Claude account', credentialSource: 'session', invocation: 'CLI' },
  { id: 'openrouter-api', label: 'OpenRouter API key', aliases: ['openrouter'], billingSource: 'key owner', credentialSource: 'OPENROUTER_API_KEY', invocation: 'HTTPS' },
];

function scriptedAsk(answers, prompts = []) {
  let index = 0;
  return async (prompt) => {
    prompts.push(prompt);
    const answer = answers[index++];
    if (answer instanceof Error) throw answer;
    return answer ?? '';
  };
}

test('normalization, consent and candidate selection fail closed', () => {
  assert.equal(normalizeAnswer('  Cláude, please!  '), 'claude please');
  assert.equal(interpretConsent("Sure, but don't do it yet."), 'no');
  assert.equal(interpretConsent('Sounds good, proceed.'), 'yes');
  assert.equal(interpretConsent('Sure, what will this cost?'), 'unknown');
  assert.equal(interpretCandidateChoice('Use Claude.', candidates).candidate.id, 'claude-account');
  assert.equal(interpretCandidateChoice('Codex or Claude.', candidates).kind, 'ambiguous');
  assert.equal(interpretCandidateChoice('Anything except Claude or OpenRouter.', candidates).candidate.id, 'codex-account');
  assert.equal(interpretCandidateChoice('Use whichever you recommend.', candidates).candidate.id, 'codex-account');
  for (const answer of ['Maybe Claude.', 'Probably Codex.', 'I guess OpenRouter.', 'Which is best?', 'The recommended one.']) {
    assert.equal(interpretCandidateChoice(answer, candidates).kind, 'unknown', answer);
  }
});

test('denial and ambiguous consent prevent verification', async () => {
  for (const answers of [['no'], ['Sure, what will this cost?', 'Maybe later.']]) {
    let calls = 0;
    const result = await runInteractiveFlow({
      candidates: [candidates[0]], begin: true, ask: scriptedAsk(answers),
      verify: async () => { calls += 1; return { ok: true }; },
    });
    assert.equal(calls, 0);
    assert.equal(result.status, 'stopped');
  }
});

test('verification interrupt prevents Socratic prompts', async () => {
  const controller = new AbortController();
  const prompts = [];
  const result = await runInteractiveFlow({
    candidates: [candidates[0]], begin: true, signal: controller.signal,
    ask: scriptedAsk(['yes'], prompts),
    verify: async (_candidate, { signal }) => new Promise((resolve) => {
      signal.addEventListener('abort', () => resolve({ ok: false, cancelled: true, reason: 'interrupt' }), { once: true });
      setTimeout(() => controller.abort(new InputEndedError('interrupt')), 10);
    }),
  });
  assert.equal(result.reason, 'interrupt');
  assert.equal(prompts.length, 1);
});

test('successful link creates only a bounded memory draft', async () => {
  const prompts = [];
  const result = await runInteractiveFlow({
    candidates: [candidates[0]], begin: true,
    ask: scriptedAsk(['yes', 'Please call me Ada.', 'Create a safe local entity.'], prompts),
    verify: async () => ({ ok: true, detail: 'Synthetic provider responded.' }),
  });
  assert.equal(result.status, 'completed');
  assert.equal(result.seed.human.preferredName, 'Ada');
  assert.equal(result.seed.entity.statedObjective, 'Create a safe local entity.');
  assert.equal(result.seed.persistence, 'memory-only');
  assert.equal(prompts.length, 3);
});

test('identity parsing and interruption reasons remain deterministic', async () => {
  assert.equal(parsePreferredName('Please call me Ada.'), 'Ada');
  assert.equal(parsePreferredName(''), 'human');
  assert.equal(createSessionSeed({ preferredName: 'Alan', objective: 'Define a system.', candidate: candidates[0] }).inference.billingSource, 'Codex account');
  for (const reason of ['eof', 'interrupt', 'timeout']) {
    let calls = 0;
    const result = await runInteractiveFlow({
      candidates: [candidates[0]], begin: true, ask: scriptedAsk([new InputEndedError(reason)]),
      verify: async () => { calls += 1; return { ok: true }; },
    });
    assert.equal(result.reason, reason);
    assert.equal(calls, 0);
  }
});
