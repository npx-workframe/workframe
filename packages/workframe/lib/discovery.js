import os from 'node:os';
import process from 'node:process';

import { VERSION } from './package-info.js';
import { buildDiscoveryEnv, firstLine, syncCommand } from './process.js';

function commandCheck(id, label, command, versionArgs = ['--version'], options = {}) {
  const result = syncCommand(command, versionArgs, options);
  return {
    id,
    label,
    command,
    status: result.ok ? 'verified' : 'missing',
    detail: result.ok ? firstLine(result.stdout || result.stderr) : '',
  };
}

function envProvider(id, label, names, env) {
  const present = names.find((name) => typeof env[name] === 'string' && env[name].trim());
  return {
    id,
    label,
    status: present ? 'configured' : 'missing',
    detail: present ? `${present} is set` : '',
    envName: present || null,
  };
}

function accountStatus(base, command, args, options) {
  if (base.status !== 'verified') return base;
  const auth = syncCommand(command, args, options);
  return {
    ...base,
    status: auth.ok ? 'authenticated' : 'detected',
    detail: auth.ok ? firstLine(auth.stdout || auth.stderr) || base.detail : base.detail,
  };
}

function hermesStatus(base, options) {
  if (base.status !== 'verified') return base;
  const doctor = syncCommand('hermes', ['doctor'], { ...options, timeout: 20_000 });
  return {
    ...base,
    status: doctor.ok ? 'verified' : 'detected',
    detail: base.detail || firstLine(doctor.stdout || doctor.stderr),
  };
}

export function collectStatus({ env = process.env } = {}) {
  const discoveryOptions = { env: buildDiscoveryEnv(env), redactionEnv: env };
  const system = [
    { id: 'node', label: 'Node.js', status: 'verified', detail: process.version },
    commandCheck('npm', 'npm', 'npm', ['--version'], discoveryOptions),
    commandCheck('git', 'Git', 'git', ['--version'], discoveryOptions),
  ];
  const docker = commandCheck('docker', 'Docker', 'docker', ['--version'], discoveryOptions);
  if (docker.status === 'verified') {
    const info = syncCommand('docker', ['info', '--format', '{{.ServerVersion}}'], discoveryOptions);
    docker.status = info.ok ? 'verified' : 'detected';
    docker.detail = info.ok ? `engine ${firstLine(info.stdout)}` : docker.detail;
  }
  system.push(docker);

  const codex = commandCheck('codex', 'Codex CLI', 'codex', ['--version'], discoveryOptions);
  const claude = commandCheck('claude', 'Claude Code', 'claude', ['--version'], discoveryOptions);
  const runtimes = [
    hermesStatus(commandCheck('hermes', 'Hermes Agent', 'hermes', ['--version'], discoveryOptions), discoveryOptions),
    accountStatus(codex, 'codex', ['login', 'status'], discoveryOptions),
    accountStatus(claude, 'claude', ['auth', 'status'], discoveryOptions),
    commandCheck('openclaw', 'OpenClaw', 'openclaw', ['--version'], discoveryOptions),
    commandCheck('pi', 'Pi', 'pi', ['--version'], discoveryOptions),
    commandCheck('cursor-agent', 'Cursor Agent', 'cursor-agent', ['--version'], discoveryOptions),
  ];
  const providers = [
    envProvider('openrouter', 'OpenRouter', ['OPENROUTER_API_KEY'], env),
    envProvider('openai', 'OpenAI', ['OPENAI_API_KEY'], env),
    envProvider('anthropic', 'Anthropic', ['ANTHROPIC_API_KEY'], env),
    envProvider('google', 'Google / Gemini', ['GEMINI_API_KEY', 'GOOGLE_API_KEY'], env),
  ];
  return { version: VERSION, platform: `${process.platform}/${process.arch}`, hostname: os.hostname(), system, runtimes, providers };
}

export function listInferenceCandidates(report) {
  const runtime = Object.fromEntries(report.runtimes.map((item) => [item.id, item]));
  const provider = Object.fromEntries(report.providers.map((item) => [item.id, item]));
  const candidates = [];
  if (runtime.codex?.status === 'authenticated') {
    candidates.push({
      id: 'codex-account', adapter: 'codex-cli', label: 'Codex CLI account',
      aliases: ['codex', 'codex account', 'chatgpt', 'chatgpt account'],
      billingSource: 'your existing Codex / ChatGPT account',
      credentialSource: 'the Codex CLI account session; no API key is injected',
      invocation: 'a cancellable read-only Codex CLI process', credentialEnvNames: [],
    });
  }
  if (runtime.claude?.status === 'authenticated') {
    candidates.push({
      id: 'claude-account', adapter: 'claude-cli', label: 'Claude Code account',
      aliases: ['claude', 'claude code', 'claude account'],
      billingSource: 'your existing Claude account',
      credentialSource: 'the Claude Code account session; no API key is injected',
      invocation: 'a cancellable read-only Claude Code process', credentialEnvNames: [],
    });
  }
  if (provider.openrouter?.status === 'configured') {
    candidates.push({
      id: 'openrouter-api', adapter: 'openrouter-http', label: 'OpenRouter API key',
      aliases: ['openrouter', 'open router', 'openrouter api'],
      billingSource: 'the owner of the configured OpenRouter API key',
      credentialSource: provider.openrouter.envName,
      invocation: 'one cancellable HTTPS request to OpenRouter', credentialEnvNames: [provider.openrouter.envName],
    });
  }
  if (provider.openai?.status === 'configured') {
    candidates.push({
      id: 'openai-api', adapter: 'openai-http', label: 'OpenAI API key',
      aliases: ['openai', 'open ai', 'openai api'],
      billingSource: 'the owner of the configured OpenAI API key',
      credentialSource: provider.openai.envName,
      invocation: 'one cancellable HTTPS request to OpenAI', credentialEnvNames: [provider.openai.envName],
    });
  }
  return candidates;
}

function marker(status, color) {
  if (['verified', 'authenticated'].includes(status)) return color.brightGreen('▶');
  if (['configured', 'detected'].includes(status)) return color.yellow('→');
  if (status === 'failed') return color.red('×');
  return color.dim('·');
}

export function printStatus(report, write, color) {
  write(color.brightGreen(`\n  WORKFRAME // LOCAL LINK CONSOLE v${VERSION}`));
  write(color.dim('  Read-only discovery. Credential values are never printed or persisted.'));
  write(color.dim(`  ${report.platform} // ${report.hostname}`));
  for (const [title, entries] of [['SYSTEM', report.system], ['AGENT RUNTIMES', report.runtimes], ['MODEL ACCESS', report.providers]]) {
    write(`\n  ${color.bold(title)}`);
    for (const entry of entries) {
      const detail = entry.detail ? color.dim(`  ${entry.detail}`) : '';
      write(`    ${marker(entry.status, color)} ${entry.label}${detail}`);
    }
  }
}
