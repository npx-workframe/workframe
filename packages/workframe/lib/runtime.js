import fs from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import process from 'node:process';

export const TIMEOUT_MS = 12_000;
export const TEST_TIMEOUT_MS = 90_000;
const isWindows = process.platform === 'win32';

export function resolveWindowsExecutable(command, env) {
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

export function spawnCommand(command, args, options) {
  const env = options.env ?? process.env;
  const executable = resolveWindowsExecutable(command, env);
  const common = {
    encoding: 'utf8',
    timeout: options.timeout ?? TIMEOUT_MS,
    cwd: options.cwd,
    env,
    shell: false,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  };

  if (isWindows && /\.(?:cmd|bat)$/i.test(executable)) {
    const commandLine = `"${[executable, ...args].map(quoteCmdArgument).join(' ')}"`;
    return spawnSync(env.ComSpec || env.COMSPEC || 'cmd.exe', ['/d', '/s', '/c', commandLine], common);
  }

  return spawnSync(executable, args, common);
}

export function run(command, args = [], options = {}) {
  const result = spawnCommand(command, args, options);
  return {
    ok: result.status === 0 && !result.error,
    code: result.status ?? 1,
    stdout: String(result.stdout ?? '').trim(),
    stderr: String(result.stderr ?? '').trim(),
    error: result.error ? String(result.error.message || result.error) : '',
  };
}

export function firstLine(value) {
  return String(value || '').split(/\r?\n/).map((line) => line.trim()).find(Boolean) || '';
}
