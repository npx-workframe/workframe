#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import { collectStatus, listInferenceCandidates, printStatus } from '../lib/discovery.js';
import { runInteractiveFlow } from '../lib/flow.js';
import { runInferenceTest } from '../lib/inference.js';
import { createTerminalDialogue } from '../lib/terminal.js';

export { collectStatus, listInferenceCandidates } from '../lib/discovery.js';
export {
  parseClaudeVerificationOutput,
  parseCodexVerificationOutput,
  parseOpenAIResponse,
  parseOpenRouterResponse,
  runInferenceTest,
} from '../lib/inference.js';
export {
  buildChildEnv,
  collectCredentialValues,
  redactSensitive,
  runCommandAsync,
} from '../lib/process.js';
export { createTerminalDialogue } from '../lib/terminal.js';

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const VERSION = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, 'package.json'), 'utf8')).version;
const QUESTION_TIMEOUT_MS = 120_000;

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

function help(write = console.log) {
  write(`workframe ${VERSION}\n\nUsage:\n  npx workframe\n  npx workframe begin\n  npx workframe status [--json] [--no-test]\n\nCommands:\n  begin      Verify an existing inference path, then begin a memory-only Socratic session.\n  status     Discover local runtimes and provider configuration.\n  help       Show this help.\n\nDiscovery is read-only. A provider call runs only after explicit approval.\nBefore approval, Workframe names the exact account or environment credential that will fund the test.\nOnly that approved path receives its required credential; values are never printed or persisted.\nCtrl+C or EOF cancels an in-flight verification and creates no draft.\nThe begin flow writes no files and changes no installation.`);
}

export async function main(args = process.argv.slice(2), dependencies = {}) {
  const parsed = parseCliArgs(args);
  const write = dependencies.write || console.log;
  const writeError = dependencies.writeError || console.error;

  if (parsed.command === 'help') {
    help(write);
    return { status: 'help' };
  }
  if (parsed.command === 'version') {
    write(VERSION);
    return { status: 'version' };
  }
  if (!['status', 'begin'].includes(parsed.command)) {
    writeError(`Unknown command: ${parsed.command}`);
    help(write);
    process.exitCode = 1;
    return { status: 'error', reason: 'unknown-command' };
  }

  const report = dependencies.report || collectStatus();
  if (parsed.json) {
    write(JSON.stringify(report, null, 2));
    return { status: 'status-json' };
  }

  printStatus(report, write);
  if (parsed.command === 'status' || parsed.noTest) return { status: 'status' };
  if (!process.stdin.isTTY && !dependencies.ask) {
    write('\n  Interactive terminal input is required for provider consent. Nothing was sent or changed.\n');
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
      verify: dependencies.verify || ((candidate, options) => runInferenceTest(candidate, options)),
      write,
      timeoutMs: dependencies.timeoutMs || QUESTION_TIMEOUT_MS,
      signal: terminal.signal,
    });
    if (result.status === 'failed') process.exitCode = 1;
    return result;
  } finally {
    terminal.close();
  }
}

function realPath(value) {
  try {
    return fs.realpathSync(value);
  } catch {
    return path.resolve(value);
  }
}

const isDirectExecution = process.argv[1]
  && realPath(process.argv[1]) === realPath(fileURLToPath(import.meta.url));
if (isDirectExecution) await main();
