import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { PassThrough } from 'node:stream';
import test from 'node:test';

import { listInferenceCandidates } from '../lib/discovery.js';
import {
  buildDiscoveryEnv, buildInferenceEnv, buildWindowsCommandLine, redactSensitive, runChildCommand,
} from '../lib/process.js';
import {
  parseClaudeVerificationOutput, parseCodexVerificationOutput, parseOpenAIResponse,
  parseOpenRouterResponse, runInferenceTest,
} from '../lib/verification.js';

const report = {
  runtimes: [
    { id: 'codex', status: 'authenticated' },
    { id: 'claude', status: 'authenticated' },
  ],
  providers: [
    { id: 'openrouter', status: 'configured', envName: 'OPENROUTER_API_KEY' },
    { id: 'openai', status: 'configured', envName: 'OPENAI_API_KEY' },
  ],
};

test('account and API-key candidates have separate exact authority', () => {
  const candidates = listInferenceCandidates(report);
  assert.deepEqual(candidates.map((item) => item.id), ['codex-account', 'claude-account', 'openrouter-api', 'openai-api']);
  assert.deepEqual(candidates[0].credentialEnvNames, []);
  assert.deepEqual(candidates[2].credentialEnvNames, ['OPENROUTER_API_KEY']);
  assert.match(candidates[0].credentialSource, /no API key/i);
  assert.match(candidates[2].billingSource, /owner/i);
});

test('detected runtimes are not represented as authenticated candidates', () => {
  const candidates = listInferenceCandidates({
    runtimes: [{ id: 'codex', status: 'detected' }, { id: 'claude', status: 'verified' }],
    providers: [],
  });
  assert.deepEqual(candidates, []);
});

test('discovery and inference environments have separate authority boundaries', () => {
  const env = {
    PATH: '/usr/bin', HOME: '/tmp/home', DOCKER_HOST: 'tcp://docker', SSH_AUTH_SOCK: '/tmp/ssh',
    OPENAI_API_KEY: 'selected', ANTHROPIC_API_KEY: 'unselected', UNRELATED_TOKEN: 'other', RANDOM: 'value',
  };
  assert.equal(buildDiscoveryEnv(env).DOCKER_HOST, 'tcp://docker');
  const account = buildInferenceEnv({ credentialEnvNames: [] }, env);
  assert.deepEqual(account, { PATH: '/usr/bin', HOME: '/tmp/home' });
  const direct = buildInferenceEnv({ credentialEnvNames: ['OPENAI_API_KEY'] }, env);
  assert.deepEqual(direct, { PATH: '/usr/bin', HOME: '/tmp/home', OPENAI_API_KEY: 'selected' });
});

test('redaction and Windows command construction fail safe', () => {
  const env = { OPENAI_API_KEY: 'selected-secret', UNRELATED_TOKEN: 'other-secret' };
  const redacted = redactSensitive('selected-secret other-secret', env);
  assert.equal(redacted.includes('secret'), false);
  assert.throws(() => buildWindowsCommandLine('tool.cmd', ['bad\narg']), /control characters/);
  assert.match(buildWindowsCommandLine('tool.cmd', ['100%', 'wow!']), /100%%/);
});

test('structured parsers require exact assistant output', () => {
  assert.equal(parseCodexVerificationOutput(JSON.stringify({ type: 'item.completed', item: { type: 'agent_message', text: 'WORKFRAME_OK' } })), true);
  assert.equal(parseCodexVerificationOutput('argv WORKFRAME_OK'), false);
  assert.equal(parseClaudeVerificationOutput(JSON.stringify({ type: 'result', subtype: 'success', result: 'WORKFRAME_OK' })), true);
  assert.equal(parseClaudeVerificationOutput(JSON.stringify({ type: 'result', subtype: 'success', result: 'Refusal WORKFRAME_OK' })), false);
  assert.equal(parseOpenAIResponse({ output: [{ type: 'message', role: 'assistant', content: [{ type: 'output_text', text: 'WORKFRAME_OK' }] }] }), true);
  assert.equal(parseOpenRouterResponse({ choices: [{ message: { content: 'Diagnostic WORKFRAME_OK' } }] }), false);
});

test('account verification injects no API key and accepts exact structured success', async () => {
  let options;
  const candidate = listInferenceCandidates(report)[0];
  const result = await runInferenceTest(candidate, {
    env: { PATH: '/usr/bin', OPENAI_API_KEY: 'must-not-leak', UNRELATED_TOKEN: 'other' },
    execute: async (_command, _args, observed) => {
      options = observed;
      return { ok: true, stdout: JSON.stringify({ type: 'item.completed', item: { type: 'agent_message', text: 'WORKFRAME_OK' } }), stderr: '' };
    },
  });
  assert.equal(result.ok, true);
  assert.deepEqual(options.env, { PATH: '/usr/bin' });
});

test('HTTP verification forwards cancellation', async () => {
  const controller = new AbortController();
  const candidate = listInferenceCandidates(report).find((item) => item.id === 'openai-api');
  const resultPromise = runInferenceTest(candidate, {
    env: { OPENAI_API_KEY: 'secret' }, signal: controller.signal,
    fetch: async (_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(options.signal.reason), { once: true });
    }),
  });
  setTimeout(() => controller.abort(), 10);
  const result = await resultPromise;
  assert.equal(result.cancelled, true);
  assert.equal(result.reason, 'interrupt');
});

test('cancellable child execution terminates an in-flight process', async () => {
  class FakeChild extends EventEmitter {
    constructor() {
      super();
      this.pid = 999999;
      this.exitCode = null;
      this.killed = false;
      this.stdout = new PassThrough();
      this.stderr = new PassThrough();
    }
    kill() { this.killed = true; this.exitCode = 1; this.emit('close', 1, 'SIGKILL'); }
  }
  const child = new FakeChild();
  const controller = new AbortController();
  const promise = runChildCommand('fake', [], {
    signal: controller.signal, platform: 'win32', spawnImpl: () => child, terminate: (target) => target.kill(), timeout: 5_000,
  });
  setTimeout(() => controller.abort(), 10);
  const result = await promise;
  assert.equal(result.cancelled, true);
  assert.equal(result.reason, 'interrupt');
});
