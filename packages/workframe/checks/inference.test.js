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

test('credential redaction covers configured secret-like environment names', () => {
  const env = {
    OPENAI_API_KEY: 'openai-secret-value',
    UNRELATED_TOKEN: 'other-secret-value',
  };
  const output = redactSensitive('failed openai-secret-value then other-secret-value', env);
  assert.equal(output.includes('openai-secret-value'), false);
  assert.equal(output.includes('other-secret-value'), false);
  assert.match(output, /\[REDACTED\]/);
});

test('inference child environment admits only base context and the selected credential', () => {
  const env = {
    PATH: '/usr/bin',
    HOME: '/tmp/home',
    OPENAI_API_KEY: 'selected-secret',
    ANTHROPIC_API_KEY: 'unselected-secret',
    UNRELATED_TOKEN: 'unrelated-secret',
    DOCKER_HOST: 'tcp://docker.example',
    DOCKER_CONTEXT: 'production',
    DOCKER_CONFIG: '/tmp/docker',
    SSH_AUTH_SOCK: '/tmp/ssh.sock',
    RANDOM_SETTING: 'not-required',
  };
  const child = buildChildEnv({ credentialEnvNames: ['OPENAI_API_KEY'] }, env, 'inference');
  assert.deepEqual(child, {
    PATH: '/usr/bin',
    HOME: '/tmp/home',
    OPENAI_API_KEY: 'selected-secret',
  });
});

test('account-backed inference receives no configured provider key', () => {
  const child = buildChildEnv({ credentialEnvNames: [] }, {
    PATH: '/usr/bin',
    HOME: '/tmp/home',
    OPENAI_API_KEY: 'must-not-leak',
    ANTHROPIC_API_KEY: 'must-not-leak-either',
  }, 'inference');
  assert.deepEqual(child, { PATH: '/usr/bin', HOME: '/tmp/home' });
});

test('discovery environment may retain Docker discovery settings but never SSH agent authority', () => {
  const child = buildChildEnv({}, {
    PATH: '/usr/bin',
    DOCKER_HOST: 'tcp://docker.example',
    DOCKER_CONTEXT: 'production',
    SSH_AUTH_SOCK: '/tmp/ssh.sock',
  }, 'discovery');
  assert.equal(child.DOCKER_HOST, 'tcp://docker.example');
  assert.equal(child.DOCKER_CONTEXT, 'production');
  assert.equal('SSH_AUTH_SOCK' in child, false);
});

test('structured verification parsers require an exact assistant result', () => {
  assert.equal(parseCodexVerificationOutput(JSON.stringify({
    type: 'item.completed',
    item: { type: 'agent_message', text: 'WORKFRAME_OK' },
  })), true);
  assert.equal(parseCodexVerificationOutput('argv: Reply with exactly WORKFRAME_OK and nothing else.'), false);
  assert.equal(parseCodexVerificationOutput(JSON.stringify({
    type: 'item.completed',
    item: { type: 'command_execution', text: 'WORKFRAME_OK' },
  })), false);

  assert.equal(parseClaudeVerificationOutput(JSON.stringify({
    type: 'result',
    subtype: 'success',
    result: 'WORKFRAME_OK',
  })), true);
  assert.equal(parseClaudeVerificationOutput(JSON.stringify({
    type: 'result',
    subtype: 'success',
    result: 'I cannot comply; the requested text was WORKFRAME_OK.',
  })), false);

  assert.equal(parseOpenAIResponse({
    output: [{ type: 'message', role: 'assistant', content: [{ type: 'output_text', text: 'WORKFRAME_OK' }] }],
  }), true);
  assert.equal(parseOpenAIResponse({
    output: [{ type: 'message', role: 'assistant', content: [{ type: 'output_text', text: 'Refusal mentioning WORKFRAME_OK.' }] }],
  }), false);
  assert.equal(parseOpenRouterResponse({ choices: [{ message: { content: 'WORKFRAME_OK' } }] }), true);
  assert.equal(parseOpenRouterResponse({ choices: [{ message: { content: 'Diagnostic mentions WORKFRAME_OK.' } }] }), false);
});

test('Codex verification rejects argv echo and redacts failed diagnostics', async () => {
  const selectedSecret = 'selected-secret-value';
  const unrelatedSecret = 'unrelated-secret-value';
  let observedOptions;
  const result = await runInferenceTest({
    id: 'codex-openai-key',
    adapter: 'codex',
    credentialEnvNames: ['OPENAI_API_KEY'],
  }, {
    env: {
      PATH: '/usr/bin',
      HOME: '/tmp/home',
      OPENAI_API_KEY: selectedSecret,
      UNRELATED_TOKEN: unrelatedSecret,
    },
    async runAsync(_command, args, options) {
      observedOptions = options;
      return {
        status: 1,
        stdout: args.join(' '),
        stderr: `failed with ${selectedSecret} and ${unrelatedSecret}`,
      };
    },
  });

  assert.equal(result.ok, false);
  assert.equal(result.detail.includes(selectedSecret), false);
  assert.equal(result.detail.includes(unrelatedSecret), false);
  assert.equal(observedOptions.env.OPENAI_API_KEY, selectedSecret);
  assert.equal('UNRELATED_TOKEN' in observedOptions.env, false);
});

test('Codex and Claude verification accept only structured exact success', async () => {
  const codex = await runInferenceTest({ id: 'codex-account', adapter: 'codex' }, {
    env: { PATH: '/usr/bin' },
    runAsync: async () => ({
      status: 0,
      stdout: JSON.stringify({ type: 'item.completed', item: { type: 'agent_message', text: 'WORKFRAME_OK' } }),
      stderr: '',
    }),
  });
  assert.equal(codex.ok, true);

  const claude = await runInferenceTest({ id: 'claude-account', adapter: 'claude' }, {
    env: { PATH: '/usr/bin' },
    runAsync: async () => ({
      status: 0,
      stdout: JSON.stringify({ type: 'result', subtype: 'success', result: 'WORKFRAME_OK' }),
      stderr: '',
    }),
  });
  assert.equal(claude.ok, true);
});

test('HTTP provider verification rejects prompt/refusal mentions and accepts exact structured output', async () => {
  const response = (payload) => ({ ok: true, status: 200, json: async () => payload });
  const refusalOpenAI = await runInferenceTest({ id: 'openai', adapter: 'openai' }, {
    env: { OPENAI_API_KEY: 'secret' },
    fetch: async () => response({
      output: [{ type: 'message', role: 'assistant', content: [{ type: 'output_text', text: 'I refuse; prompt requested WORKFRAME_OK.' }] }],
    }),
  });
  assert.equal(refusalOpenAI.ok, false);

  const refusalOpenRouter = await runInferenceTest({ id: 'openrouter', adapter: 'openrouter' }, {
    env: { OPENROUTER_API_KEY: 'secret' },
    fetch: async () => response({ choices: [{ message: { content: 'The requested token was WORKFRAME_OK.' } }] }),
  });
  assert.equal(refusalOpenRouter.ok, false);

  const exactOpenRouter = await runInferenceTest({ id: 'openrouter', adapter: 'openrouter' }, {
    env: { OPENROUTER_API_KEY: 'secret' },
    fetch: async () => response({ choices: [{ message: { content: 'WORKFRAME_OK' } }] }),
  });
  assert.equal(exactOpenRouter.ok, true);
});

for (const reason of ['eof', 'interrupt', 'timeout']) {
  test(`${reason} before consent stops without provider invocation`, async () => {
    let verificationCalls = 0;
    const result = await runInteractiveFlow({
      candidates: [candidates[0]],
      begin: true,
      ask: scriptedAsk([new InputEndedError(reason)]),
      verify: async () => {
        verificationCalls += 1;
        return { ok: true };
      },
    });

    assert.equal(result.reason, reason);
    assert.equal(verificationCalls, 0);
  });
}

test('verification-phase interruption cancels the provider and prevents Socratic prompts', async () => {
  const controller = new AbortController();
  const prompts = [];
  let cancellationObserved = false;
  const resultPromise = runInteractiveFlow({
    candidates: [candidates[0]],
    begin: true,
    ask: scriptedAsk(['yes'], prompts),
    signal: controller.signal,
    verify: async (_candidate, { signal }) => new Promise((_resolve, reject) => {
      signal.addEventListener('abort', () => {
        cancellationObserved = true;
        reject(abortError());
      }, { once: true });
      setTimeout(() => controller.abort(new InputEndedError('interrupt')), 20);
    }),
  });

  const result = await resultPromise;
  assert.equal(result.status, 'stopped');
  assert.equal(result.reason, 'interrupt');
  assert.equal(cancellationObserved, true);
  assert.equal(prompts.length, 1);
});

test('real child process is terminated promptly when verification signal aborts', async () => {
  const controller = new AbortController();
  const startedAt = Date.now();
  const pending = runCommandAsync(process.execPath, ['-e', 'setTimeout(() => {}, 60000)'], {
    signal: controller.signal,
    timeout: 60_000,
    env: process.env,
  });
  setTimeout(() => controller.abort(new InputEndedError('interrupt')), 50);
  await assert.rejects(pending, (error) => error?.name === 'AbortError' && error?.reason === 'interrupt');
  assert.ok(Date.now() - startedAt < 2_000);
});

test('HTTP verification receives and obeys the external cancellation signal', async () => {
  const controller = new AbortController();
  let observedSignal;
  const pending = runInferenceTest({ id: 'openai', adapter: 'openai' }, {
    env: { OPENAI_API_KEY: 'secret' },
    signal: controller.signal,
    fetch: async (_url, options) => {
      observedSignal = options.signal;
      return new Promise((_resolve, reject) => {
        options.signal.addEventListener('abort', () => reject(abortError()), { once: true });
      });
    },
  });
  setTimeout(() => controller.abort(new InputEndedError('interrupt')), 20);
  await assert.rejects(pending, (error) => error?.name === 'AbortError' && error?.reason === 'interrupt');
  assert.equal(observedSignal.aborted, true);
});
