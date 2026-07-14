import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { EventEmitter } from 'node:events';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { PassThrough } from 'node:stream';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import {
  buildChildEnv,
  createTerminalDialogue,
  listInferenceCandidates,
  parseClaudeVerificationOutput,
  parseCodexVerificationOutput,
  parseOpenAIResponse,
  parseOpenRouterResponse,
  redactSensitive,
  runCommandAsync,
  runInferenceTest,
} from '../bin/workframe.js';
import {
  interpretCandidateChoice,
  interpretConsent,
  normalizeAnswer,
} from '../lib/dialogue.js';
import { InputEndedError, runInteractiveFlow } from '../lib/flow.js';
import { createSessionSeed, parsePreferredName } from '../lib/session.js';

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const CLI = path.join(PACKAGE_ROOT, 'bin', 'workframe.js');
const candidates = [
  {
    id: 'codex-account',
    label: 'Codex CLI (ChatGPT account)',
    aliases: ['codex', 'codex account'],
    billing: 'the existing Codex account',
    credentialDisclosure: 'No provider API key will be injected into this runtime process.',
  },
  {
    id: 'claude-account',
    label: 'Claude Code (local account)',
    aliases: ['claude', 'claude account'],
    billing: 'the existing Claude account',
    credentialDisclosure: 'No provider API key will be injected into this runtime process.',
  },
  {
    id: 'openrouter',
    label: 'OpenRouter (direct API)',
    aliases: ['openrouter', 'open router'],
    billing: 'the configured OpenRouter account',
    credentialDisclosure: 'OPENROUTER_API_KEY will be available only to this approved path.',
  },
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

class FakeReadlineInterface extends EventEmitter {
  constructor() {
    super();
    this.closed = false;
    this.questionCallback = null;
  }

  question(_prompt, callback) {
    if (this.closed) {
      const error = new Error('Interface closed');
      error.code = 'ERR_USE_AFTER_CLOSE';
      throw error;
    }
    this.questionCallback = callback;
  }

  answer(value) {
    const callback = this.questionCallback;
    this.questionCallback = null;
    callback?.(value);
  }

  close() {
    if (this.closed) return;
    this.closed = true;
    this.emit('close');
  }
}

function createTerminalHarness() {
  const input = new EventEmitter();
  const output = new PassThrough();
  const signals = new EventEmitter();
  const rl = new FakeReadlineInterface();
  const terminal = createTerminalDialogue({
    input,
    output,
    signals,
    createInterface: () => rl,
  });
  return { input, rl, signals, terminal };
}

async function assertInputEnded(promise, reason) {
  await assert.rejects(promise, (error) => {
    assert.ok(error instanceof InputEndedError);
    assert.equal(error.reason, reason);
    return true;
  });
}

function abortError() {
  const error = new Error('aborted');
  error.name = 'AbortError';
  return error;
}

test('normalizeAnswer removes accents and punctuation without inventing intent', () => {
  assert.equal(normalizeAnswer('  Cláude, please!  '), 'claude please');
});

test('negative consent overrides positive language', () => {
  assert.equal(interpretConsent("Sure, but don't do it yet."), 'no');
  assert.equal(interpretConsent('Yes, not now.'), 'no');
});

test('consent requires an unqualified explicit affirmative', () => {
  assert.equal(interpretConsent('Sounds good, proceed.'), 'yes');
  assert.equal(interpretConsent('Sure, what will this cost?'), 'unknown');
  assert.equal(interpretConsent('Okay, explain what will be sent first.'), 'unknown');
  assert.equal(interpretConsent("Yes, if it's free."), 'unknown');
  assert.equal(interpretConsent('Tell me more first.'), 'unknown');
});

test('candidate choice resolves one explicit natural-language mention', () => {
  const result = interpretCandidateChoice('Use Claude Code for this.', candidates);
  assert.equal(result.kind, 'selected');
  assert.equal(result.candidate.id, 'claude-account');
});

test('candidate choice refuses to guess between multiple paths', () => {
  const result = interpretCandidateChoice('Codex or Claude would both be fine.', candidates);
  assert.equal(result.kind, 'ambiguous');
  assert.deepEqual(result.candidates.map((candidate) => candidate.id), ['codex-account', 'claude-account']);
});

test('candidate choice honors exclusions', () => {
  const result = interpretCandidateChoice('Anything except Claude or OpenRouter.', candidates);
  assert.equal(result.kind, 'selected');
  assert.equal(result.candidate.id, 'codex-account');
});

test('candidate choice uses deterministic order only when delegated', () => {
  const result = interpretCandidateChoice('Use whichever you recommend.', candidates);
  assert.equal(result.kind, 'selected');
  assert.equal(result.candidate.id, 'codex-account');
});

test('candidate questions and non-imperative preferences do not delegate selection', () => {
  assert.equal(interpretCandidateChoice('Which one is best?', candidates).kind, 'unknown');
  assert.equal(interpretCandidateChoice('What is the default?', candidates).kind, 'unknown');
  assert.equal(interpretCandidateChoice('Should I use Claude?', candidates).kind, 'unknown');
  assert.equal(interpretCandidateChoice('The recommended one.', candidates).kind, 'unknown');
  assert.equal(interpretCandidateChoice('Best.', candidates).kind, 'unknown');
});

test('hedged candidate choices remain unresolved', () => {
  for (const answer of ['Maybe Claude.', 'Perhaps Codex.', 'Probably OpenRouter.', 'I guess Claude.', 'I think Codex.', 'Not sure, Claude.']) {
    assert.equal(interpretCandidateChoice(answer, candidates).kind, 'unknown', answer);
  }
});

test('imperative best/default language delegates selection explicitly', () => {
  assert.equal(interpretCandidateChoice('Use the best available option.', candidates).candidate.id, 'codex-account');
  assert.equal(interpretCandidateChoice('Pick the default.', candidates).candidate.id, 'codex-account');
});

test('runtime candidates separate account and API-key billing paths', () => {
  const report = {
    runtimes: [
      { id: 'codex', status: 'authenticated' },
      { id: 'claude', status: 'verified' },
    ],
    providers: [
      { id: 'openai', status: 'configured', envName: 'OPENAI_API_KEY' },
      { id: 'anthropic', status: 'configured', envName: 'ANTHROPIC_API_KEY' },
      { id: 'openrouter', status: 'missing', envName: null },
    ],
  };
  const paths = listInferenceCandidates(report);
  assert.deepEqual(paths.map((candidate) => candidate.id), [
    'codex-account',
    'codex-openai-key',
    'claude-account',
    'claude-anthropic-key',
    'openai',
  ]);
  assert.deepEqual(paths.find((candidate) => candidate.id === 'codex-account').credentialEnvNames, []);
  assert.deepEqual(paths.find((candidate) => candidate.id === 'codex-openai-key').credentialEnvNames, ['OPENAI_API_KEY']);
  assert.match(paths.find((candidate) => candidate.id === 'codex-openai-key').billing, /OPENAI_API_KEY/);
});

test('plain runtime name is ambiguous when account and key variants both exist', () => {
  const variants = [
    { id: 'codex-account', label: 'Codex CLI (ChatGPT account)', aliases: ['codex'] },
    { id: 'codex-openai-key', label: 'Codex CLI (OpenAI API key)', aliases: ['codex'] },
  ];
  assert.equal(interpretCandidateChoice('Use Codex.', variants).kind, 'ambiguous');
  assert.equal(interpretCandidateChoice('Use the Codex account.', variants).candidate.id, 'codex-account');
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
    candidate: { id: 'codex-account', label: 'Codex CLI (ChatGPT account)' },
  });

  assert.deepEqual(seed, {
    status: 'draft',
    persistence: 'memory-only',
    human: { preferredName: 'Alan' },
    entity: {
      statedObjective: 'Build a system that helps me define and deploy an entity.',
      unresolved: ['purpose', 'constraints', 'success criteria'],
    },
    inference: { id: 'codex-account', label: 'Codex CLI (ChatGPT account)', status: 'verified' },
  });
});

test('denial prevents provider invocation and Socratic prompts', async () => {
  let verificationCalls = 0;
  const prompts = [];
  const result = await runInteractiveFlow({
    candidates: [candidates[0]],
    begin: true,
    ask: scriptedAsk(['no'], prompts),
    verify: async () => {
      verificationCalls += 1;
      return { ok: true };
    },
  });

  assert.equal(result.reason, 'declined');
  assert.equal(verificationCalls, 0);
  assert.equal(prompts.length, 1);
});

test('ambiguous consent remains fail closed after one clarification', async () => {
  let verificationCalls = 0;
  const result = await runInteractiveFlow({
    candidates: [candidates[0]],
    begin: true,
    ask: scriptedAsk(['Sure, what will this cost?', 'Maybe after you explain.']),
    verify: async () => {
      verificationCalls += 1;
      return { ok: true };
    },
  });

  assert.equal(result.reason, 'ambiguous-consent');
  assert.equal(verificationCalls, 0);
});

test('failed verification prevents identity and objective prompts', async () => {
  const prompts = [];
  const result = await runInteractiveFlow({
    candidates: [candidates[0]],
    begin: true,
    ask: scriptedAsk(['yes'], prompts),
    verify: async () => ({ ok: false, detail: 'synthetic failure' }),
  });

  assert.equal(result.reason, 'verification-failed');
  assert.equal(prompts.length, 1);
});

test('verified link gates the memory-only Socratic seed', async () => {
  const prompts = [];
  const result = await runInteractiveFlow({
    candidates: [candidates[0]],
    begin: true,
    ask: scriptedAsk(['yes', 'Please call me Ada.', 'Create a safe local entity.'], prompts),
    verify: async () => ({ ok: true, detail: 'Synthetic provider responded.' }),
  });

  assert.equal(result.status, 'completed');
  assert.equal(result.seed.human.preferredName, 'Ada');
  assert.equal(result.seed.entity.statedObjective, 'Create a safe local entity.');
  assert.equal(prompts.length, 3);
});

test('missing objective stops without a persisted draft', async () => {
  const result = await runInteractiveFlow({
    candidates: [candidates[0]],
    begin: true,
    ask: scriptedAsk(['yes', 'Ada', '   ']),
    verify: async () => ({ ok: true }),
  });

  assert.equal(result.reason, 'missing-objective');
  assert.equal('seed' in result, false);
});
