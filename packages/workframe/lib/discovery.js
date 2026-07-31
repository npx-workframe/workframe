import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { firstLine, run } from './runtime.js';

function commandCheck(id, label, command, versionArgs = ['--version']) {
  const result = run(command, versionArgs);
  return {
    id,
    label,
    command,
    status: result.ok ? 'verified' : 'missing',
    detail: result.ok ? firstLine(result.stdout || result.stderr) : '',
  };
}

function envProvider(id, label, names) {
  const present = names.find((name) => typeof process.env[name] === 'string' && process.env[name].trim());
  return {
    id,
    label,
    status: present ? 'configured' : 'missing',
    detail: present ? `${present} is set` : '',
    envName: present || null,
  };
}

function codexStatus(base) {
  if (base.status !== 'verified') return base;
  const login = run('codex', ['login', 'status']);
  return {
    ...base,
    status: login.ok ? 'authenticated' : 'detected',
    detail: login.ok ? firstLine(login.stdout || login.stderr) || base.detail : base.detail,
  };
}

function hermesStatus(base) {
  if (base.status !== 'verified') return base;
  const doctor = run('hermes', ['doctor'], { timeout: 20_000 });
  return {
    ...base,
    status: doctor.ok ? 'verified' : 'detected',
    detail: base.detail || firstLine(doctor.stdout || doctor.stderr),
  };
}

export function collectStatus(version) {
  const system = [
    { id: 'node', label: 'Node.js', status: 'verified', detail: process.version },
    commandCheck('npm', 'npm', 'npm'),
    commandCheck('git', 'Git', 'git'),
  ];

  const docker = commandCheck('docker', 'Docker', 'docker');
  if (docker.status === 'verified') {
    const info = run('docker', ['info', '--format', '{{.ServerVersion}}']);
    docker.status = info.ok ? 'verified' : 'detected';
    docker.detail = info.ok ? `engine ${firstLine(info.stdout)}` : docker.detail;
  }
  system.push(docker);

  const runtimes = [
    hermesStatus(commandCheck('hermes', 'Hermes Agent', 'hermes')),
    codexStatus(commandCheck('codex', 'Codex CLI', 'codex')),
    commandCheck('claude', 'Claude Code', 'claude'),
    commandCheck('openclaw', 'OpenClaw', 'openclaw'),
    commandCheck('pi', 'Pi', 'pi'),
    commandCheck('cursor-agent', 'Cursor Agent', 'cursor-agent'),
  ];

  const providers = [
    envProvider('openrouter', 'OpenRouter', ['OPENROUTER_API_KEY']),
    envProvider('openai', 'OpenAI', ['OPENAI_API_KEY']),
    envProvider('anthropic', 'Anthropic', ['ANTHROPIC_API_KEY']),
    envProvider('google', 'Google / Gemini', ['GEMINI_API_KEY', 'GOOGLE_API_KEY']),
  ];

  return {
    version,
    platform: `${process.platform}/${process.arch}`,
    hostname: os.hostname(),
    system,
    runtimes,
    providers,
  };
}
