import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { EventEmitter } from 'node:events';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { PassThrough } from 'node:stream';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import { InputEndedError } from '../lib/flow.js';
import { createTerminalDialogue } from '../lib/terminal.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const CLI = path.join(ROOT, 'bin', 'workframe.js');

class FakeReadline extends EventEmitter {
  question(_prompt, callback) { this.callback = callback; }
  answer(value) { this.callback?.(value); }
  close() { this.emit('close'); }
}

function terminalHarness() {
  const input = new EventEmitter();
  const signals = new EventEmitter();
  const rl = new FakeReadline();
  const terminal = createTerminalDialogue({ input, output: new PassThrough(), signals, createInterface: () => rl });
  return { input, signals, rl, terminal };
}

async function assertEnded(promise, reason) {
  await assert.rejects(promise, (error) => error instanceof InputEndedError && error.reason === reason);
}

test('terminal answers normally and aborts pending input on SIGINT', async () => {
  const normal = terminalHarness();
  const answer = normal.terminal.ask('> ', { timeoutMs: 1_000 });
  normal.rl.answer('yes');
  assert.equal(await answer, 'yes');
  normal.terminal.close();

  const interrupted = terminalHarness();
  const pending = interrupted.terminal.ask('> ', { timeoutMs: 1_000 });
  interrupted.signals.emit('SIGINT');
  await assertEnded(pending, 'interrupt');
  assert.equal(interrupted.terminal.signal.aborted, true);
  interrupted.terminal.close();
});

test('terminal distinguishes timeout and EOF', async () => {
  const timeout = terminalHarness();
  await assertEnded(timeout.terminal.ask('> ', { timeoutMs: 5 }), 'timeout');
  timeout.terminal.close();
  const eof = terminalHarness();
  const pending = eof.terminal.ask('> ', { timeoutMs: 1_000 });
  eof.input.emit('end');
  await assertEnded(pending, 'eof');
  eof.terminal.close();
});

test('package executable works directly and through POSIX symlink', () => {
  const direct = spawnSync(process.execPath, [CLI, '--version'], { encoding: 'utf8' });
  assert.equal(direct.status, 0, direct.stderr);
  assert.match(direct.stdout.trim(), /^\d+\.\d+\.\d+$/);
  if (process.platform !== 'win32') {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'workframe-bin-'));
    const linked = path.join(directory, 'workframe');
    try {
      fs.symlinkSync(CLI, linked);
      const result = spawnSync(process.execPath, [linked, '--version'], { encoding: 'utf8' });
      assert.equal(result.status, 0, result.stderr);
    } finally {
      fs.rmSync(directory, { recursive: true, force: true });
    }
  }
});

test('status JSON contains provider names but no credential values', () => {
  const secret = 'wf-test-secret-value';
  const result = spawnSync(process.execPath, [CLI, 'status', '--json'], {
    encoding: 'utf8', env: { ...process.env, OPENAI_API_KEY: secret },
  });
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.providers.find((provider) => provider.id === 'openai').status, 'configured');
  assert.equal(result.stdout.includes(secret), false);
});

test('help states consent, cancellation and persistence boundaries', () => {
  const result = spawnSync(process.execPath, [CLI, 'help'], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /exact payer and credential source/i);
  assert.match(result.stdout, /Ctrl\+C cancels/i);
  assert.match(result.stdout, /writes no files/i);
});
