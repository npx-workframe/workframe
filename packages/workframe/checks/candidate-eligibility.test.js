import assert from 'node:assert/strict';
import test from 'node:test';

import { listInferenceCandidates } from '../lib/discovery.js';

function report({ claudeStatus = 'missing', anthropicStatus = 'missing' } = {}) {
  return {
    runtimes: [
      { id: 'codex', status: 'missing' },
      { id: 'claude', status: claudeStatus },
    ],
    providers: [
      { id: 'openrouter', status: 'missing', envName: null },
      { id: 'openai', status: 'missing', envName: null },
      {
        id: 'anthropic',
        status: anthropicStatus,
        envName: anthropicStatus === 'configured' ? 'ANTHROPIC_API_KEY' : null,
      },
    ],
  };
}

test('installed Claude CLI does not imply an authenticated account path', () => {
  const candidates = listInferenceCandidates(report({ claudeStatus: 'verified' }));
  assert.equal(candidates.some((candidate) => candidate.id === 'claude-account'), false);
});

test('authenticated Claude status enables the account-backed path without a provider key', () => {
  const candidates = listInferenceCandidates(report({ claudeStatus: 'authenticated' }));
  const account = candidates.find((candidate) => candidate.id === 'claude-account');

  assert.ok(account);
  assert.deepEqual(account.credentialEnvNames, []);
  assert.match(account.billing, /authenticated local Claude Code account or session/);
});

test('configured Anthropic key remains a separate Claude path', () => {
  const candidates = listInferenceCandidates(report({
    claudeStatus: 'verified',
    anthropicStatus: 'configured',
  }));

  assert.equal(candidates.some((candidate) => candidate.id === 'claude-account'), false);
  const keyPath = candidates.find((candidate) => candidate.id === 'claude-anthropic-key');
  assert.ok(keyPath);
  assert.deepEqual(keyPath.credentialEnvNames, ['ANTHROPIC_API_KEY']);
  assert.match(keyPath.billing, /ANTHROPIC_API_KEY/);
});
