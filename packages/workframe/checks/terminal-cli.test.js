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

test('terminal adapter resolves a normal answer', async () => {
  const { rl, terminal } = createTerminalHarness();
  const pending = terminal.ask('> ', { timeoutMs: 1_000 });
  rl.answer('yes');
  assert.equal(await pending, 'yes');
  terminal.close();
});

test('terminal adapter settles a pending question and aborts its lifecycle on process SIGINT', async () => {
  const { signals, terminal } = createTerminalHarness();
  const pending = terminal.ask('> ', { timeoutMs: 1_000 });
  signals.emit('SIGINT');
  await assertInputEnded(pending, 'interrupt');
  assert.equal(terminal.signal.aborted, true);
  assert.equal(terminal.signal.reason.reason, 'interrupt');
  terminal.close();
});

test('terminal adapter also handles readline SIGINT', async () => {
  const { rl, terminal } = createTerminalHarness();
  const pending = terminal.ask('> ', { timeoutMs: 1_000 });
  rl.emit('SIGINT');
  await assertInputEnded(pending, 'interrupt');
  terminal.close();
});

test('terminal adapter distinguishes timeout from EOF', async () => {
  const timeoutHarness = createTerminalHarness();
  await assertInputEnded(timeoutHarness.terminal.ask('> ', { timeoutMs: 5 }), 'timeout');
  timeoutHarness.terminal.close();

  const eofHarness = createTerminalHarness();
  const pending = eofHarness.terminal.ask('> ', { timeoutMs: 1_000 });
  eofHarness.input.emit('end');
  await assertInputEnded(pending, 'eof');
  eofHarness.terminal.close();
});

test('terminal SIGINT during verification aborts the in-flight operation', async () => {
  const { rl, signals, terminal } = createTerminalHarness();
  let verificationStarted;
  const started = new Promise((resolve) => { verificationStarted = resolve; });
  let cancellationObserved = false;
  const flow = runInteractiveFlow({
    candidates: [candidates[0]],
    begin: true,
    ask: terminal.ask,
    signal: terminal.signal,
    verify: async (_candidate, { signal }) => new Promise((_resolve, reject) => {
      verificationStarted();
      signal.addEventListener('abort', () => {
        cancellationObserved = true;
        reject(abortError());
      }, { once: true });
    }),
  });
  while (!rl.questionCallback) await new Promise((resolve) => setImmediate(resolve));
  rl.answer('yes');
  await started;
  signals.emit('SIGINT');
  const result = await flow;
  assert.equal(result.reason, 'interrupt');
  assert.equal(cancellationObserved, true);
  terminal.close();
});

test('real readline adapter settles when its input stream ends', async () => {
  const input = new PassThrough();
  const output = new PassThrough();
  const terminal = createTerminalDialogue({ input, output });
  const pending = terminal.ask('> ', { timeoutMs: 1_000 });
  input.end();
  await assertInputEnded(pending, 'eof');
  terminal.close();
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

test('help states exact billing, credential, and cancellation boundaries', () => {
  const result = spawnSync(process.execPath, [CLI, 'help'], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /exact account or environment credential/i);
  assert.match(result.stdout, /never printed or persisted/i);
  assert.match(result.stdout, /Ctrl\+C or EOF cancels/i);
  assert.doesNotMatch(result.stdout, /never printed or transmitted/i);
});
