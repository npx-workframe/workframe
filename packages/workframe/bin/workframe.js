#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import { collectStatus, listInferenceCandidates, printStatus } from '../lib/discovery.js';
import { runInteractiveFlow } from '../lib/flow.js';
import { QUESTION_TIMEOUT_MS, VERSION } from '../lib/package-info.js';
import { createTerminalDialogue } from '../lib/terminal.js';
import { runInferenceTest } from '../lib/verification.js';

export { collectStatus, listInferenceCandidates } from '../lib/discovery.js';
export { createTerminalDialogue } from '../lib/terminal.js';
export {
  abortReason, buildDiscoveryEnv, buildInferenceEnv, buildWindowsCommandLine,
  collectCredentialValues, quoteCmdArgument, redactSensitive, resolveWindowsExecutable,
  runChildCommand,
} from '../lib/process.js';
export {
  parseClaudeVerificationOutput, parseCodexVerificationOutput, parseOpenAIResponse,
  parseOpenRouterResponse, runInferenceTest,
} from '../lib/verification.js';

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

export function parseCliArgs(args) {
  if (args.includes('--version') || args.includes('-v')) return { command: 'version', json: false };
  if (args.includes('--help') || args.includes('-h')) return { command: 'help', json: false };
  return { command: args.find((arg) => !arg.startsWith('-')) || 'status', json: args.includes('--json') };
}

function help(write = console.log) {
  write(`workframe ${VERSION}\n\nUsage:\n  npx workframe\n  npx workframe begin\n  npx workframe status [--json]\n\nCommands:\n  begin      Verify one existing inference path, then create a memory-only first mirror.\n  status     Discover local runtimes and provider configuration without inference.\n  help       Show this help.\n\nDiscovery is read-only. A provider call runs only after explicit approval of one exact payer and credential source.\nOnly the approved credential is sent to the approved provider; it is never printed or persisted.\nCtrl+C cancels a pending verification. The begin flow writes no files and changes no installation.`);
}

export async function main(args = process.argv.slice(2), dependencies = {}) {
  const parsed = parseCliArgs(args);
  const write = dependencies.write || console.log;
  const writeError = dependencies.writeError || console.error;
  if (parsed.command === 'help') { help(write); return { status: 'help' }; }
  if (parsed.command === 'version') { write(VERSION); return { status: 'version' }; }
  if (!['status', 'begin'].includes(parsed.command)) {
    writeError(`Unknown command: ${parsed.command}`);
    help(write);
    process.exitCode = 1;
    return { status: 'error', reason: 'unknown-command' };
  }

  const report = dependencies.report || collectStatus();
  if (parsed.json) { write(JSON.stringify(report, null, 2)); return { status: 'status-json' }; }
  printStatus(report, write, color);
  if (parsed.command === 'status') return { status: 'status' };
  if (!process.stdin.isTTY && !dependencies.ask) {
    write(color.dim('\n  Interactive terminal input is required for provider consent. Nothing was sent or changed.\n'));
    return { status: 'stopped', reason: 'non-interactive' };
  }

  const terminal = dependencies.ask
    ? { ask: dependencies.ask, signal: dependencies.signal, close: () => {} }
    : createTerminalDialogue();
  try {
    const result = await runInteractiveFlow({
      candidates: dependencies.candidates || listInferenceCandidates(report),
      begin: true,
      ask: terminal.ask,
      verify: dependencies.verify || ((candidate, { signal }) => runInferenceTest(candidate, { signal })),
      signal: terminal.signal,
      write,
      timeoutMs: dependencies.timeoutMs || QUESTION_TIMEOUT_MS,
    });
    if (result.status === 'failed') process.exitCode = 1;
    return result;
  } finally {
    terminal.close();
  }
}

function realPath(value) {
  try { return fs.realpathSync(value); } catch { return path.resolve(value); }
}
const isDirectExecution = process.argv[1]
  && realPath(process.argv[1]) === realPath(fileURLToPath(import.meta.url));
if (isDirectExecution) await main();
