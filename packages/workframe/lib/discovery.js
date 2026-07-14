import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import { buildChildEnv, run } from './process.js';

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const VERSION = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, 'package.json'), 'utf8')).version;
const isTTY = Boolean(process.stdout.isTTY && process.env.TERM !== 'dumb');
const noColor = 'NO_COLOR' in process.env && process.env.NO_COLOR !== '0';
const useColor = isTTY && !noColor;
const color = {
  brightGreen: (value) => useColor ? `\x1b[92m${value}\x1b[0m` : value,
  yellow: (value) => useColor ? `\x1b[33m${value}\x1b[0m` : value,
  red: (value) => useColor ? `\x1b[31m${value}\x1b[0m` : value,
  dim: (value) => useColor ? `\x1b[2m${value}\x1b[0m` : value,
  bold: (value) => useColor ? `\x1b[1m${value}\x1b[0m` : value,
};

function firstLine(value) {
  return String(value || '').split(/\r?\n/).map((line) => line.trim()).find(Boolean) || '';
}

function commandCheck(id, label, command, versionArgs = ['--version'], options = {}) {
  const result = run(command, versionArgs, options);
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

function codexStatus(base, options) {
  if (base.status !== 'verified') return base;
  const login = run('codex', ['login', 'status'], options);
  return {
    ...base,
    status: login.ok ? 'authenticated' : 'detected',
    detail: login.ok ? firstLine(login.stdout || login.stderr) || base.detail : base.detail,
  };
}

function hermesStatus(base, options) {
  if (base.status !== 'verified') return base;
  const doctor = run('hermes', ['doctor'], { ...options, timeout: 20_000 });
  return {
    ...base,
    status: doctor.ok ? 'verified' : 'detected',
    detail: base.detail || firstLine(doctor.stdout || doctor.stderr),
  };
}

export function collectStatus() {
  const discoveryOptions = {
    env: buildChildEnv({}, process.env, 'discovery'),
    redactionEnv: process.env,
  };
  const system = [
    { id: 'node', label: 'Node.js', status: 'verified', detail: process.version },
    commandCheck('npm', 'npm', 'npm', ['--version'], discoveryOptions),
    commandCheck('git', 'Git', 'git', ['--version'], discoveryOptions),
  ];

  const docker = commandCheck('docker', 'Docker', 'docker', ['--version'], discoveryOptions);
  if (docker.status === 'verified') {
    const info = run('docker', ['info', '--format', '{{.ServerVersion}}'], discoveryOptions);
    docker.status = info.ok ? 'verified' : 'detected';
    docker.detail = info.ok ? `engine ${firstLine(info.stdout)}` : docker.detail;
  }
  system.push(docker);

  const runtimes = [
    hermesStatus(commandCheck('hermes', 'Hermes Agent', 'hermes', ['--version'], discoveryOptions), discoveryOptions),
    codexStatus(commandCheck('codex', 'Codex CLI', 'codex', ['--version'], discoveryOptions), discoveryOptions),
    commandCheck('claude', 'Claude Code', 'claude', ['--version'], discoveryOptions),
    commandCheck('openclaw', 'OpenClaw', 'openclaw', ['--version'], discoveryOptions),
    commandCheck('pi', 'Pi', 'pi', ['--version'], discoveryOptions),
    commandCheck('cursor-agent', 'Cursor Agent', 'cursor-agent', ['--version'], discoveryOptions),
  ];

  const providers = [
    envProvider('openrouter', 'OpenRouter', ['OPENROUTER_API_KEY']),
    envProvider('openai', 'OpenAI', ['OPENAI_API_KEY']),
    envProvider('anthropic', 'Anthropic', ['ANTHROPIC_API_KEY']),
    envProvider('google', 'Google / Gemini', ['GEMINI_API_KEY', 'GOOGLE_API_KEY']),
  ];

  return {
    version: VERSION,
    platform: `${process.platform}/${process.arch}`,
    hostname: os.hostname(),
    system,
    runtimes,
    providers,
  };
}

function marker(status) {
  if (['verified', 'authenticated'].includes(status)) return color.brightGreen('▶');
  if (['configured', 'detected'].includes(status)) return color.yellow('→');
  if (status === 'failed') return color.red('×');
  return color.dim('·');
}

function printGroup(title, entries, write = console.log) {
  write(`\n  ${color.bold(title)}`);
  for (const entry of entries) {
    const detail = entry.detail ? color.dim(`  ${entry.detail}`) : '';
    write(`    ${marker(entry.status)} ${entry.label}${detail}`);
  }
}

export function printStatus(report, write = console.log) {
  write(color.brightGreen(`\n  WORKFRAME // LOCAL LINK CONSOLE v${VERSION}`));
  write(color.dim('  Read-only discovery. Credential values are never printed or persisted.'));
  write(color.dim(`  ${report.platform} // ${report.hostname}`));
  printGroup('SYSTEM', report.system, write);
  printGroup('AGENT RUNTIMES', report.runtimes, write);
  printGroup('MODEL ACCESS', report.providers, write);
}

function runtimePresent(runtime) {
  return runtime && ['authenticated', 'verified', 'detected'].includes(runtime.status);
}

function accountCandidate({ id, label, aliases, adapter, billing }) {
  return {
    id,
    label,
    aliases,
    adapter,
    billing,
    credentialEnvNames: [],
    credentialDisclosure: 'No provider API key will be injected into this runtime process.',
  };
}

function keyCandidate({ id, label, aliases, adapter, billing, envName }) {
  return {
    id,
    label,
    aliases,
    adapter,
    billing,
    credentialEnvNames: [envName],
    credentialDisclosure: `${envName} will be available only to this approved inference path for the bounded test.`,
  };
}

export function listInferenceCandidates(report) {
  const runtime = Object.fromEntries(report.runtimes.map((item) => [item.id, item]));
  const provider = Object.fromEntries(report.providers.map((item) => [item.id, item]));
  const candidates = [];

  if (runtime.codex?.status === 'authenticated') {
    candidates.push(accountCandidate({
      id: 'codex-account',
      label: 'Codex CLI (ChatGPT account)',
      aliases: ['codex', 'codex account', 'chatgpt account'],
      adapter: 'codex',
      billing: 'your authenticated Codex / ChatGPT account',
    }));
  }
  if (runtimePresent(runtime.codex) && provider.openai?.status === 'configured') {
    candidates.push(keyCandidate({
      id: 'codex-openai-key',
      label: 'Codex CLI (OpenAI API key)',
      aliases: ['codex', 'codex openai key', 'codex api key'],
      adapter: 'codex',
      billing: `the OpenAI account associated with ${provider.openai.envName}`,
      envName: provider.openai.envName,
    }));
  }
  if (runtime.claude?.status === 'authenticated') {
    candidates.push(accountCandidate({
      id: 'claude-account',
      label: 'Claude Code (local account)',
      aliases: ['claude', 'claude account'],
      adapter: 'claude',
      billing: 'the authenticated local Claude Code account or session',
    }));
  }
  if (runtimePresent(runtime.claude) && provider.anthropic?.status === 'configured') {
    candidates.push(keyCandidate({
      id: 'claude-anthropic-key',
      label: 'Claude Code (Anthropic API key)',
      aliases: ['claude', 'claude anthropic key', 'claude api key'],
      adapter: 'claude',
      billing: `the Anthropic account associated with ${provider.anthropic.envName}`,
      envName: provider.anthropic.envName,
    }));
  }
  if (provider.openrouter?.status === 'configured') {
    candidates.push(keyCandidate({
      id: 'openrouter',
      label: 'OpenRouter (direct API)',
      aliases: ['openrouter', 'open router'],
      adapter: 'openrouter',
      billing: `the OpenRouter account associated with ${provider.openrouter.envName}`,
      envName: provider.openrouter.envName,
    }));
  }
  if (provider.openai?.status === 'configured') {
    candidates.push(keyCandidate({
      id: 'openai',
      label: 'OpenAI (direct API)',
      aliases: ['openai', 'open ai'],
      adapter: 'openai',
      billing: `the OpenAI account associated with ${provider.openai.envName}`,
      envName: provider.openai.envName,
    }));
  }

  return candidates;
}
