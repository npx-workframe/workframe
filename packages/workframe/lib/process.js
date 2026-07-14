import fs from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';
import path from 'node:path';
import process from 'node:process';

import { InputEndedError } from './flow.js';

const TIMEOUT_MS = 12_000;
const CREDENTIAL_NAME_PATTERN = /(?:API_?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH)/i;
const BASE_CHILD_ENV_NAMES = new Set([
  'PATH', 'Path', 'PATHEXT', 'SystemRoot', 'SYSTEMROOT', 'COMSPEC', 'ComSpec',
  'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'APPDATA', 'LOCALAPPDATA',
  'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'TMP', 'TEMP', 'TMPDIR', 'LANG', 'LC_ALL',
  'TERM', 'NO_COLOR', 'CI',
]);
const DISCOVERY_CHILD_ENV_NAMES = new Set([
  ...BASE_CHILD_ENV_NAMES,
  'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_CONFIG',
]);
const isWindows = process.platform === 'win32';

function resolveWindowsExecutable(command, env) {
  if (!isWindows) return command;
  if (/[\\/]/.test(command)) return command;

  const pathEntries = String(env.PATH || env.Path || '')
    .split(path.delimiter)
    .map((entry) => entry.trim().replace(/^"|"$/g, ''))
    .filter(Boolean);
  const extensions = path.extname(command)
    ? ['']
    : String(env.PATHEXT || '.COM;.EXE;.BAT;.CMD')
      .split(';')
      .map((extension) => extension.trim().toLowerCase())
      .filter(Boolean);

  for (const directory of pathEntries) {
    for (const extension of extensions) {
      const candidate = path.join(directory, `${command}${extension}`);
      try {
        if (fs.statSync(candidate).isFile()) return candidate;
      } catch {
        // Continue through PATH candidates.
      }
    }
  }

  return command;
}

function quoteCmdArgument(value) {
  const text = String(value);
  if (/[\0\r\n]/.test(text)) throw new Error('Command arguments may not contain control characters.');
  return `"${text.replace(/%/g, '%%').replace(/!/g, '^!').replace(/"/g, '\\"')}"`;
}

function resolveSpawnSpec(command, args, env) {
  const executable = resolveWindowsExecutable(command, env);
  if (isWindows && /\.(?:cmd|bat)$/i.test(executable)) {
    const commandLine = `"${[executable, ...args].map(quoteCmdArgument).join(' ')}"`;
    return {
      command: env.ComSpec || env.COMSPEC || 'cmd.exe',
      args: ['/d', '/s', '/c', commandLine],
    };
  }
  return { command: executable, args };
}

function spawnCommandSync(command, args, options) {
  const env = options.env ?? process.env;
  const spec = resolveSpawnSpec(command, args, env);
  return spawnSync(spec.command, spec.args, {
    encoding: 'utf8',
    timeout: options.timeout ?? TIMEOUT_MS,
    cwd: options.cwd,
    env,
    shell: false,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
}

export function createAbortError(reason = 'aborted') {
  const error = new Error(`Operation aborted: ${reason}`);
  error.name = 'AbortError';
  error.reason = reason;
  return error;
}

export function abortReason(signal) {
  const reason = signal?.reason;
  if (reason instanceof InputEndedError) return reason.reason;
  if (typeof reason?.reason === 'string') return reason.reason;
  if (typeof reason === 'string') return reason;
  return 'aborted';
}

export function runCommandAsync(command, args = [], options = {}) {
  const env = options.env ?? process.env;
  const timeout = options.timeout ?? TIMEOUT_MS;
  const signal = options.signal;
  const spec = resolveSpawnSpec(command, args, env);

  if (signal?.aborted) return Promise.reject(createAbortError(abortReason(signal)));

  return new Promise((resolve, reject) => {
    let child;
    let stdout = '';
    let stderr = '';
    let settled = false;
    let timedOut = false;
    let killTimer = null;

    const finish = (callback, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeoutTimer);
      clearTimeout(killTimer);
      signal?.removeEventListener?.('abort', onAbort);
      callback(value);
    };

    const terminate = () => {
      if (!child || child.killed) return;
      try {
        child.kill('SIGTERM');
      } catch {
        // The close/error path will settle the promise.
      }
      killTimer = setTimeout(() => {
        try {
          if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL');
        } catch {
          // The close/error path will settle the promise.
        }
      }, 500);
      killTimer.unref?.();
    };

    const onAbort = () => terminate();
    const timeoutTimer = setTimeout(() => {
      timedOut = true;
      terminate();
    }, timeout);
    timeoutTimer.unref?.();

    try {
      child = spawn(spec.command, spec.args, {
        cwd: options.cwd,
        env,
        shell: false,
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    } catch (error) {
      finish(resolve, { status: null, stdout, stderr, error });
      return;
    }

    signal?.addEventListener?.('abort', onAbort, { once: true });
    if (signal?.aborted) onAbort();
    child.stdout?.setEncoding('utf8');
    child.stderr?.setEncoding('utf8');
    child.stdout?.on('data', (chunk) => { stdout += chunk; });
    child.stderr?.on('data', (chunk) => { stderr += chunk; });
    child.once('error', (error) => finish(resolve, { status: null, stdout, stderr, error }));
    child.once('close', (code, closeSignal) => {
      if (signal?.aborted) {
        finish(reject, createAbortError(abortReason(signal)));
        return;
      }
      if (timedOut) {
        finish(resolve, {
          status: code,
          signal: closeSignal,
          stdout,
          stderr,
          error: new Error(`Command timed out after ${timeout}ms.`),
        });
        return;
      }
      finish(resolve, { status: code, signal: closeSignal, stdout, stderr });
    });
  });
}

export function collectCredentialValues(env = process.env) {
  return Object.entries(env)
    .filter(([name, value]) => CREDENTIAL_NAME_PATTERN.test(name) && typeof value === 'string' && value.length >= 4)
    .map(([, value]) => value)
    .sort((left, right) => right.length - left.length);
}

export function redactSensitive(value, env = process.env) {
  let redacted = String(value ?? '');
  for (const secret of collectCredentialValues(env)) {
    redacted = redacted.split(secret).join('[REDACTED]');
  }
  return redacted;
}

export function buildChildEnv(candidate, sourceEnv = process.env, purpose = 'inference') {
  const allowedNames = purpose === 'discovery' ? DISCOVERY_CHILD_ENV_NAMES : BASE_CHILD_ENV_NAMES;
  const childEnv = {};
  for (const [name, value] of Object.entries(sourceEnv)) {
    if (allowedNames.has(name) && typeof value === 'string') childEnv[name] = value;
  }
  for (const name of candidate.credentialEnvNames || []) {
    const value = sourceEnv[name];
    if (typeof value === 'string' && value) childEnv[name] = value;
  }
  return childEnv;
}

export function sanitizeExecutionResult(result, env = process.env) {
  return {
    ok: Boolean(result?.ok ?? (result?.status === 0 && !result?.error)),
    code: result?.code ?? result?.status ?? 1,
    stdout: redactSensitive(result?.stdout ?? '', env).trim(),
    stderr: redactSensitive(result?.stderr ?? '', env).trim(),
    error: redactSensitive(result?.error?.message ?? result?.error ?? '', env).trim(),
  };
}

export function run(command, args = [], options = {}) {
  const result = spawnCommandSync(command, args, options);
  return sanitizeExecutionResult(result, options.redactionEnv ?? process.env);
}
