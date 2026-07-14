import fs from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';
import path from 'node:path';
import process from 'node:process';

import { InputEndedError } from './flow.js';
import { DISCOVERY_TIMEOUT_MS, VERIFICATION_TIMEOUT_MS } from './package-info.js';

const MAX_CHILD_OUTPUT_BYTES = 1_000_000;
const CREDENTIAL_NAME_PATTERN = /(?:API_?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH)/i;
const BASE_CHILD_ENV_NAMES = new Set([
  'PATH', 'Path', 'PATHEXT', 'SystemRoot', 'SYSTEMROOT', 'COMSPEC', 'ComSpec',
  'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'APPDATA', 'LOCALAPPDATA',
  'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'TMP', 'TEMP', 'TMPDIR', 'LANG', 'LC_ALL',
  'TERM', 'NO_COLOR', 'CI',
]);
const DISCOVERY_ONLY_ENV_NAMES = new Set(['DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_CONFIG']);

export function resolveWindowsExecutable(command, env, platform = process.platform) {
  if (platform !== 'win32' || /[\\/]/.test(command)) return command;
  const pathEntries = String(env.PATH || env.Path || '')
    .split(';')
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

export function quoteCmdArgument(value) {
  const text = String(value);
  if (/[\0\r\n]/.test(text)) throw new Error('Command arguments may not contain control characters.');
  return `"${text.replace(/%/g, '%%').replace(/!/g, '^!').replace(/"/g, '\\"')}"`;
}

export function buildWindowsCommandLine(executable, args) {
  return `"${[executable, ...args].map(quoteCmdArgument).join(' ')}"`;
}

export function collectCredentialValues(env = process.env) {
  return Object.entries(env)
    .filter(([name, value]) => CREDENTIAL_NAME_PATTERN.test(name) && typeof value === 'string' && value.length >= 4)
    .map(([, value]) => value)
    .sort((left, right) => right.length - left.length);
}

export function redactSensitive(value, env = process.env) {
  let redacted = String(value ?? '');
  for (const secret of collectCredentialValues(env)) redacted = redacted.split(secret).join('[REDACTED]');
  return redacted;
}

export function buildDiscoveryEnv(sourceEnv = process.env) {
  return Object.fromEntries(Object.entries(sourceEnv).filter(([name, value]) => (
    (BASE_CHILD_ENV_NAMES.has(name) || DISCOVERY_ONLY_ENV_NAMES.has(name)) && typeof value === 'string'
  )));
}

export function buildInferenceEnv(candidate, sourceEnv = process.env) {
  const childEnv = Object.fromEntries(Object.entries(sourceEnv).filter(([name, value]) => (
    BASE_CHILD_ENV_NAMES.has(name) && typeof value === 'string'
  )));
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
    cancelled: Boolean(result?.cancelled),
    reason: result?.reason || null,
  };
}

export function firstLine(value) {
  return String(value || '').split(/\r?\n/).map((line) => line.trim()).find(Boolean) || '';
}

export function syncCommand(command, args = [], options = {}) {
  const env = options.env ?? process.env;
  const platform = options.platform ?? process.platform;
  const executable = resolveWindowsExecutable(command, env, platform);
  const common = {
    encoding: 'utf8',
    timeout: options.timeout ?? DISCOVERY_TIMEOUT_MS,
    cwd: options.cwd,
    env,
    shell: false,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  };
  const result = platform === 'win32' && /\.(?:cmd|bat)$/i.test(executable)
    ? spawnSync(env.ComSpec || env.COMSPEC || 'cmd.exe', ['/d', '/s', '/c', buildWindowsCommandLine(executable, args)], common)
    : spawnSync(executable, args, common);
  return sanitizeExecutionResult(result, options.redactionEnv ?? process.env);
}

export function abortReason(signal, fallback = 'interrupt') {
  const reason = signal?.reason;
  if (reason instanceof InputEndedError) return reason.reason;
  if (typeof reason?.reason === 'string') return reason.reason;
  if (reason?.name === 'TimeoutError') return 'timeout';
  return fallback;
}

function terminateChild(child, platform) {
  if (!child || child.exitCode !== null || child.killed) return;
  try {
    if (platform === 'win32') {
      spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'], { stdio: 'ignore', shell: false, windowsHide: true }).unref();
    } else {
      process.kill(-child.pid, 'SIGTERM');
      const forceTimer = setTimeout(() => {
        try { process.kill(-child.pid, 'SIGKILL'); } catch { /* The child group already exited. */ }
      }, 500);
      forceTimer.unref?.();
    }
  } catch {
    try { child.kill('SIGKILL'); } catch { /* The child already exited. */ }
  }
}

export function runChildCommand(command, args = [], options = {}) {
  const env = options.env ?? process.env;
  const platform = options.platform ?? process.platform;
  const executable = resolveWindowsExecutable(command, env, platform);
  const signal = options.signal;
  const timeoutMs = options.timeout ?? VERIFICATION_TIMEOUT_MS;
  const spawnImpl = options.spawnImpl ?? spawn;
  const terminate = options.terminate ?? terminateChild;
  const useCmd = platform === 'win32' && /\.(?:cmd|bat)$/i.test(executable);
  const childCommand = useCmd ? env.ComSpec || env.COMSPEC || 'cmd.exe' : executable;
  const childArgs = useCmd ? ['/d', '/s', '/c', buildWindowsCommandLine(executable, args)] : args;

  if (signal?.aborted) {
    return Promise.resolve({ ok: false, code: 1, stdout: '', stderr: '', error: '', cancelled: true, reason: abortReason(signal) });
  }

  return new Promise((resolve) => {
    let settled = false;
    let stdout = '';
    let stderr = '';
    let cancelled = false;
    let cancelReason = null;
    let cancelSettleTimer;
    const child = spawnImpl(childCommand, childArgs, {
      cwd: options.cwd,
      env,
      shell: false,
      windowsHide: true,
      detached: platform !== 'win32',
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    const finish = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      clearTimeout(cancelSettleTimer);
      signal?.removeEventListener?.('abort', onAbort);
      resolve(sanitizeExecutionResult({ ...result, stdout, stderr, cancelled, reason: cancelReason }, options.redactionEnv ?? process.env));
    };
    const append = (current, chunk) => {
      if (Buffer.byteLength(current) >= MAX_CHILD_OUTPUT_BYTES) return current;
      const next = current + String(chunk);
      return Buffer.byteLength(next) > MAX_CHILD_OUTPUT_BYTES
        ? Buffer.from(next).subarray(0, MAX_CHILD_OUTPUT_BYTES).toString('utf8')
        : next;
    };
    child.stdout?.on('data', (chunk) => { stdout = append(stdout, chunk); });
    child.stderr?.on('data', (chunk) => { stderr = append(stderr, chunk); });

    const cancel = (reason) => {
      cancelled = true;
      cancelReason = reason;
      terminate(child, platform);
      cancelSettleTimer = setTimeout(() => finish({ ok: false, code: 1, error: '' }), 750);
      cancelSettleTimer.unref?.();
    };
    const onAbort = () => cancel(abortReason(signal));
    signal?.addEventListener?.('abort', onAbort, { once: true });
    const timer = setTimeout(() => cancel('timeout'), timeoutMs);
    timer.unref?.();

    child.once('error', (error) => finish({ ok: false, code: 1, error }));
    child.once('close', (code, closeSignal) => finish({
      ok: !cancelled && code === 0,
      code: code ?? 1,
      error: closeSignal && !cancelled ? `Process ended with signal ${closeSignal}` : '',
    }));
  });
}
