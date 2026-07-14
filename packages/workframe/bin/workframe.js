#!/usr/bin/env node

import fs from 'node:fs';
import { spawnSync } from 'node:child_process';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import readline from 'node:readline/promises';
import { fileURLToPath } from 'node:url';

import { interpretCandidateChoice, interpretConsent } from '../lib/dialogue.js';
import { cleanFreeText, createSessionSeed } from '../lib/session.js';

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const VERSION = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, 'package.json'), 'utf8')).version;
const TIMEOUT_MS = 12_000;
const TEST_TIMEOUT_MS = 90_000;
const isWindows = process.platform === 'win32';
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

function spawnCommand(command, args, options) {
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

function run(command, args = [], options = {}) {
  const result = spawnCommand(command, args, options);
  return {
    ok: result.status === 0 && !result.error,
    code: result.status ?? 1,
    stdout: String(result.stdout ?? '').trim(),
    stderr: String(result.stderr ?? '').trim(),
    error: result.error ? String(result.error.message || result.error) : '',
  };
}

function firstLine(value) {
  return String(value || '').split(/\r?\n/).map((line) => line.trim()).find(Boolean) || '';
}

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

export function collectStatus() {
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

function printGroup(title, entries) {
  console.log(`\n  ${color.bold(title)}`);
  for (const entry of entries) {
    const detail = entry.detail ? color.dim(`  ${entry.detail}`) : '';
    console.log(`    ${marker(entry.status)} ${entry.label}${detail}`);
  }
}

function printStatus(report) {
  console.log(color.brightGreen(`\n  WORKFRAME // LOCAL LINK CONSOLE v${VERSION}`));
  console.log(color.dim('  Read-only discovery. No credentials or inventory are transmitted.'));
  console.log(color.dim(`  ${report.platform} // ${report.hostname}`));
  printGroup('SYSTEM', report.system);
  printGroup('AGENT RUNTIMES', report.runtimes);
  printGroup('MODEL ACCESS', report.providers);
}

function listInferenceCandidates(report) {
  const runtime = Object.fromEntries(report.runtimes.map((item) => [item.id, item]));
  const provider = Object.fromEntries(report.providers.map((item) => [item.id, item]));
  const candidates = [];

  if (runtime.codex?.status === 'authenticated') {
    candidates.push({
      id: 'codex',
      label: 'Codex CLI',
      aliases: ['codex'],
      billing: 'your existing Codex / ChatGPT account or configured provider',
    });
  }
  if (runtime.claude?.status === 'verified') {
    candidates.push({
      id: 'claude',
      label: 'Claude Code',
      aliases: ['claude'],
      billing: 'your existing Claude account or Anthropic provider',
    });
  }
  if (provider.openrouter?.status === 'configured') {
    candidates.push({
      id: 'openrouter',
      label: 'OpenRouter',
      aliases: ['open router'],
      billing: 'the OpenRouter key already present in your environment',
    });
  }
  if (provider.openai?.status === 'configured') {
    candidates.push({
      id: 'openai',
      label: 'OpenAI',
      aliases: ['open ai'],
      billing: 'the OpenAI key already present in your environment',
    });
  }

  return candidates;
}

async function testOpenAI() {
  const response = await fetch('https://api.openai.com/v1/responses', {
    method: 'POST',
    headers: {
      authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model: 'gpt-4o-mini',
      input: 'Reply with exactly WORKFRAME_OK and nothing else.',
      max_output_tokens: 8,
    }),
    signal: AbortSignal.timeout(30_000),
  });
  const body = await response.text();
  return { ok: response.ok && /WORKFRAME_OK/i.test(body), detail: response.ok ? 'OpenAI responded.' : `OpenAI returned HTTP ${response.status}.` };
}

async function testOpenRouter() {
  const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      authorization: `Bearer ${process.env.OPENROUTER_API_KEY}`,
      'content-type': 'application/json',
      'x-title': 'Workframe local link test',
    },
    body: JSON.stringify {
      model: 'openai/gpt-4o-mini',
      messages: [{ role: 'user', content: 'Reply with exactly WORKFRAME_OK and nothing else.' }],
      max_tokens: 8,
      temperature: 0,
    }),
    signal: AbortSignal.timeout(30_000),
  });
  const body = await response.text();
  return { ok: response.ok && /WORKFRAME_OK/i.test(body), detail: response.ok ? 'OpenRouter responded.' : `OpenRouter returned HTTP ${response.status}.` };
}

async function runTest(candidate) {
  if (candidate.id === 'codex') {
    const result = run('codex', [
      'exec',
      '--skip-git-repo-check',
      '--sandbox', 'read-only',
      '--color', 'never',
      'Reply with exactly WORKFRAME_OK and nothing else. Do not inspect files or run tools.',
    ], { timeout: TEST_TIMEOUT_MS, cwd: os.tmpdir() });
    return { ok: result.ok && /WORKFRAME_OK/i.test(`${result.stdout}\n${result.stderr}`), detail: result.ok ? 'Codex responded.' : firstLine(result.stderr || result.error || 'Codex test failed.') };
  }
  if (candidate.id === 'claude') {
    const result = run('claude', [
      '-p',
      '--permission-mode', 'plan',
      '--max-turns', '1',
      '--max-budget-usd', '0.02',
      '--no-session-persistence',
      'Reply with exactly WORKFRAME_OK and nothing else.',
    ], { timeout: TEST_TIMEOUT_MS, cwd: os.tmpdir() });
    return { ok: result.ok && /WORKFRAME_OK/i.test(`${result.stdout}\n${result.stderr}`), detail: result.ok ? 'Claude responded.' : firstLine(result.stderr || result.error || 'Claude test failed.') };
  }
  if (candidate.id === 'openrouter') return testOpenRouter();
  if (candidate.id === 'openai') return testOpenAI();
  return { ok: false, detail: 'No test adapter is available.' };
}

async function selectCandidate(rl, candidates) {
  if (candidates.length === 1) return candidates[0];

  console.log('\n  I found more than one inference path I can test:');
  for (const candidate of candidates) {
    console.log(`    ${marker('verified')} ${candidate.label}`);
  }

  let answer = await rl.question('\n  Which one should we speak through?\n  > ');
  let selection = interpretCandidateChoice(answer, candidates);
  if (selection.kind === 'selected') return selection.candidate;

  const reason = selection.kind === 'ambiguous'
    ? 'You named more than one path.'
    : 'I could not tell which path you meant.';
  answer = await rl.question(`\n  ${reason} Name one, or tell me to use the recommended one.\n  > `);
  selection = interpretCandidateChoice(answer, candidates);
  return selection.kind === 'selected' ? selection.candidate : null;
}

async function verifyInferenceLink(report, rl) {
  const candidates = listInferenceCandidates(report);
  if (candidates.length === 0) {
    console.log(color.dim('\n  I could not find a configured inference path I can test safely.'));
    console.log(color.dim('  Nothing was sent and nothing was changed. We stop here.\n'));
    return null;
  }

  const candidate = await selectCandidate(rl, candidates);
  if (!candidate) {
    console.log(color.dim('\n  I still could not resolve one path safely. Nothing was sent or changed.\n'));
    return null;
  }

  console.log(`\n  I can make one tiny verification call through ${color.bold(candidate.label)}.`);
  console.log(color.dim(`  It will use ${candidate.billing} and may incur a negligible charge.`));
  console.log(color.dim('  Nothing else will be installed or changed.'));

  let answer = await rl.question('\n  Shall I test the link?\n  > ');
  let consent = interpretConsent(answer);
  if (consent === 'unknown') {
    answer = await rl.question('\n  I could not tell whether that was a yes or a no. Say it naturally, but make the intent explicit.\n  > ');
    consent = interpretConsent(answer);
  }

  if (consent !== 'yes') {
    console.log(color.dim('\n  Understood. Nothing was sent and nothing was changed.\n'));
    return null;
  }

  console.log(color.dim(`\n  Opening a minimal link through ${candidate.label}...`));
  try {
    const result = await runTest(candidate);
    if (!result.ok) {
      console.log(color.red('  × LINK FAILED'));
      console.log(color.dim(`  ${result.detail}\n`));
      process.exitCode = 1;
      return null;
    }

    console.log(color.brightGreen('  ▶ LINK VERIFIED'));
    console.log(color.dim(`  ${result.detail}\n`));
    return candidate;
  } catch (error) {
    console.log(color.red('  × LINK FAILED'));
    console.log(color.dim(`  ${error instanceof Error ? error.message : String(error)}\n`));
    process.exitCode = 1;
    return null;
  }
}

async function beginSocraticSession(rl, candidate) {
  console.log(color.brightGreen('\n  Welcome home, human.'));
  console.log(color.dim('  We will begin with what is true now. This is a draft, not a commitment.'));

  const nameAnswer = await rl.question('\n  Before we define a system, who is speaking? What should I call you?\n  > ');
  const objective = cleanFreeText(await rl.question('\n  What are you trying to bring into existence, change, or understand?\n  > '));

  if (!objective) {
    console.log(color.dim('\n  I do not yet have a stated objective to mirror.'));
    console.log(color.dim('  No files were written and nothing was installed or changed.\n'));
    return null;
  }

  const seed = createSessionSeed({ preferredName: nameAnswer, objective, candidate });
  console.log(`\n  ${color.bold('MIRROR // FIRST DRAFT')}`);
  console.log(`    Human: ${seed.human.preferredName}`);
  console.log(`    Stated aim: ${seed.entity.statedObjective}`);
  console.log(`    Inference path: ${seed.inference.label} (${seed.inference.status})`);
  console.log('    Open questions: purpose, constraints, success criteria');
  console.log(color.dim('\n  I have mirrored only what you said.'));
  console.log(color.dim('  This draft exists in memory only. No files were written.'));
  console.log(color.dim('  No package, runtime, agent, or Workframe installation was changed.\n'));
  return seed;
}

async function runInteractive(report, { begin }) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try {
    const candidate = await verifyInferenceLink(report, rl);
    if (candidate && begin) await beginSocraticSession(rl, candidate);
  } finally {
    rl.close();
  }
}

export function parseCliArgs(args) {
  if (args.includes('--version') || args.includes('-v')) return { command: 'version', json: false, noTest: true };
  if (args.includes('--help') || args.includes('-h')) return { command: 'help', json: false, noTest: true };

  const command = args.find((arg) => !arg.startsWith('-')) || 'status';
  return {
    command,
    json: args.includes('--json'),
    noTest: args.includes('--no-test') || args.includes('--json'),
  };
}

function help() {
  console.log(`workframe ${VERSION}\n\nUsage:\n  npx workframe\n  npx workframe begin\n  npx workframe status [--json] [--no-test]\n\nCommands:\n  begin      Verify an existing inference path, then begin a memory-only Socratic session.\n  status     Discover local runtimes and provider configuration.\n  help       Show this help.\n\nDiscovery is read-only. A provider call runs only after explicit approval.\nThe begin flow writes no files and changes no installation.\nCredential values are never printed or transmitted by Workframe.`);
}

export async function main(args = process.argv.slice(2)) {
  const parsed = parseCliArgs(args);

  if (parsed.command === 'help') {
    help();
    return;
  }
  if (parsed.command === 'version') {
    console.log(VERSION);
    return;
  }
  if (!['status', 'begin'].includes(parsed.command)) {
    console.error(`Unknown command: ${parsed.command}`);
    help();
    process.exitCode = 1;
    return;
  }

  const report = collectStatus();
  if (parsed.json) {
    console.log(JSON.stringify(report, null, 2));
    return;
  }

  printStatus(report);
  const noTest = parsed.noTest || !process.stdin.isTTY;
  if (!noTest) await runInteractive(report, { begin: parsed.command === 'begin' });
}

await main();
