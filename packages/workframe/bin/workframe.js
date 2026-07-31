#!/usr/bin/env node

import fs from 'node:fs';
import readline from 'node:readline/promises';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { runBegin, printBeginMirror } from '../lib/begin.js';
import { collectStatus } from '../lib/discovery.js';
import { buildCapabilityGraph, listEligibleVerificationCandidates } from '../lib/capability-graph.js';
import { resolveCandidateSelection } from '../lib/inference-selection.js';
import { runVerification, chooseTestCandidate, runLegacyTest } from '../lib/inference.js';
import { buildConstitutionalDraft, BEGIN_QUESTIONS } from '../lib/mirror.js';
import { buildApplyBundle, evaluateApplyGate } from '../lib/apply-gate.js';
import { executeApply, preflightApply } from '../lib/apply-executor.js';
import { interpretConsent } from '../lib/text.js';
import { createInteractiveAsk, seedFromFlags, findFlagValue } from '../lib/cli-args.js';

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

async function askForLegacyTest(report) {
  const candidate = chooseTestCandidate(report);
  if (!candidate) {
    console.log(color.dim('\n  I could not find a configured inference path I can test safely.'));
    console.log(color.dim('  Nothing was sent and nothing was changed. We stop here.\n'));
    return;
  }

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try {
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
      return;
    }

    console.log(color.dim(`\n  Opening a minimal link through ${candidate.label}...`));
    try {
      const result = await runLegacyTest(candidate);
      if (result.ok) {
        console.log(color.brightGreen('  ▶ LINK VERIFIED'));
        console.log(color.dim(`  ${result.detail}\n`));
      } else {
        console.log(color.red('  × LINK FAILED'));
        console.log(color.dim(`  ${result.detail}\n`));
        process.exitCode = 1;
      }
    } catch (error) {
      console.log(color.red('  × LINK FAILED'));
      console.log(color.dim(`  ${error instanceof Error ? error.message : String(error)}\n`));
      process.exitCode = 1;
    }
  } finally {
    rl.close();
  }
}

function help() {
  console.log(`workframe ${VERSION}

Usage:
  npx workframe
  npx workframe status [--json] [--no-test]
  npx workframe begin [--json] [--human=...] [--entity=...] ...
  npx workframe capabilities [--json]
  npx workframe verify [--json] [--select="use codex"]
  npx workframe draft [--json] [--human=...] ...
  npx workframe plan [--json] [--target=path] ...
  npx workframe apply [--execute] [--json] [--target=path] [--approval="approve plan ..."]
  npx workframe origin [--json] [--target=path]

Commands:
  status        Discover local runtimes and provider configuration.
  begin         Memory-only Socratic entry — no network, no writes.
  capabilities  Truthful capability graph without auto-selection.
  verify        Explicit-path verification with separate consent.
  draft         Constitutional in-memory draft from begin fields.
  plan          Dry-run Architectonic + deployment plans.
  apply         Gated instantiate (--execute runs architectonic init + optional cell).
  origin        Begin interview + show plan hash and approval phrase.
  help          Show this help.

Credential values are never printed or transmitted by Workframe.`);
}

async function cmdBegin(args) {
  const json = args.includes('--json');
  const seed = seedFromFlags(args);
  const interactive = createInteractiveAsk();
  const { mirror } = await runBegin({
    json,
    seed,
    ask: Object.keys(seed).length === BEGIN_QUESTIONS.length ? null : interactive.ask,
    close: interactive.close,
  });

  if (json) {
    console.log(JSON.stringify(mirror, null, 2));
    return;
  }
  printBeginMirror(mirror, color);
}

async function cmdCapabilities(args) {
  const json = args.includes('--json');
  const report = collectStatus(VERSION);
  const graph = buildCapabilityGraph(report);
  if (json) {
    console.log(JSON.stringify(graph, null, 2));
    return;
  }
  console.log(color.brightGreen('\n  WORKFRAME // CAPABILITY GRAPH'));
  for (const candidate of graph.candidates) {
    console.log(`  ${color.bold(candidate.id)} — ${candidate.label} (${candidate.eligibility})`);
  }
  console.log(color.dim('\n  No path is selected automatically.\n'));
}

async function cmdVerify(args) {
  const json = args.includes('--json');
  const report = collectStatus(VERSION);
  const graph = buildCapabilityGraph(report);
  const eligible = listEligibleVerificationCandidates(graph);
  const selectText = findFlagValue(args, '--select') || '';

  if (!eligible.length) {
    const out = { ok: false, reason: 'no_eligible_candidates', candidates: graph.candidates };
    if (json) console.log(JSON.stringify(out, null, 2));
    else console.log(color.dim('\n  No eligible verification path. Nothing sent.\n'));
    return;
  }

  let selection = selectText ? resolveCandidateSelection(selectText, eligible) : { status: 'unresolved' };
  if (selection.status !== 'selected') {
    const out = { ok: false, reason: selection.reason || 'selection_required', eligible: eligible.map((c) => c.id) };
    if (json) console.log(JSON.stringify(out, null, 2));
    else {
      console.log(color.yellow('\n  Name one path explicitly. Example: use codex'));
      console.log(color.dim(`  Eligible: ${eligible.map((c) => c.id).join(', ')}\n`));
    }
    return;
  }

  const candidate = selection.candidate;
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  let consent = 'no';
  if (!json && process.stdin.isTTY) {
    console.log(`\n  Selected ${candidate.label}. Payer: ${candidate.payer}.`);
    const answer = await rl.question('\n  Explicit consent required. Proceed with one minimal verification call?\n  > ');
    consent = interpretConsent(answer);
  }
  rl.close();

  if (consent !== 'yes') {
    const out = { ok: false, reason: 'consent_denied', candidate: candidate.id };
    if (json) console.log(JSON.stringify(out, null, 2));
    else console.log(color.dim('\n  Consent not given. Nothing sent.\n'));
    return;
  }

  const controller = new AbortController();
  const result = await runVerification(candidate, { signal: controller.signal });
  const out = { ok: result.ok, cancelled: result.cancelled, candidate: candidate.id, detail: result.detail };
  if (json) console.log(JSON.stringify(out, null, 2));
  else if (result.ok) console.log(color.brightGreen('\n  ▶ VERIFIED\n'));
  else console.log(color.red(`\n  × ${result.detail}\n`));
  if (!result.ok) process.exitCode = 1;
}

async function cmdDraft(args) {
  const json = args.includes('--json');
  const seed = seedFromFlags(args);
  const { mirror } = await runBegin({ json: true, seed, ask: null });
  const draft = buildConstitutionalDraft(mirror);
  if (json) console.log(JSON.stringify(draft, null, 2));
  else console.log(JSON.stringify(draft, null, 2));
}

async function sessionFromArgs(args) {
  const seed = seedFromFlags(args);
  const targetRoot = findFlagValue(args, '--target');
  const { mirror } = await runBegin({ json: true, seed, ask: null });
  const draft = buildConstitutionalDraft(mirror);
  const report = collectStatus(VERSION);
  const bundle = buildApplyBundle(draft, report, { targetRoot });
  return { mirror, draft, bundle };
}

async function cmdPlan(args) {
  const json = args.includes('--json');
  const { bundle } = await sessionFromArgs(args);
  const out = { architectonic: bundle.architectonic, deployment: bundle.deployment, plan_hash: bundle.plan_hash };
  if (json) console.log(JSON.stringify(out, null, 2));
  else console.log(JSON.stringify(out, null, 2));
}

async function cmdApply(args) {
  const json = args.includes('--json');
  const execute = args.includes('--execute');
  const approval = findFlagValue(args, '--approval') || '';
  const { draft, bundle } = await sessionFromArgs(args);
  const gate = evaluateApplyGate({ bundle, approvalText: approval, execute });
  const out = {
    ...gate,
    preflight: preflightApply(bundle),
    bundle: { plan_hash: bundle.plan_hash, target_root: bundle.architectonic.target_root },
  };

  if (!gate.approved) {
    if (json) console.log(JSON.stringify(out, null, 2));
    else console.log(`\n  ${gate.message}\n`);
    return;
  }

  if (execute) {
    if (!out.preflight.ok) {
      out.result = { ok: false, reason: 'preflight_failed', preflight: out.preflight };
      process.exitCode = 1;
    } else {
      out.result = executeApply(bundle, draft);
      if (!out.result.ok) process.exitCode = 1;
    }
  }

  if (json) console.log(JSON.stringify(out, null, 2));
  else {
    console.log(`\n  ${gate.message}`);
    if (out.result) console.log(JSON.stringify(out.result, null, 2));
    console.log('');
  }
}

async function cmdOrigin(args) {
  const json = args.includes('--json');
  const targetRoot = findFlagValue(args, '--target');
  const seed = seedFromFlags(args);
  const seededAll = BEGIN_QUESTIONS.every((question) => seed[question.key]);
  const interactive = createInteractiveAsk();
  const { mirror } = await runBegin({
    json: true,
    seed,
    ask: seededAll ? null : interactive.ask,
    close: interactive.close,
  });
  const draft = buildConstitutionalDraft(mirror);
  const report = collectStatus(VERSION);
  const bundle = buildApplyBundle(draft, report, { targetRoot });
  const preflight = preflightApply(bundle);
  const approvalPhrase = `approve plan ${bundle.plan_hash}`;

  const summary = {
    mirror,
    draft,
    plan_hash: bundle.plan_hash,
    architectonic: bundle.architectonic,
    deployment: bundle.deployment,
    preflight,
    approval_phrase: approvalPhrase,
  };

  if (json) {
    console.log(JSON.stringify(summary, null, 2));
    return;
  }

  printBeginMirror(mirror, color);
  console.log(color.brightGreen('\n  WORKFRAME // ORIGIN'));
  console.log(color.dim(`  Target: ${bundle.architectonic.target_root}`));
  console.log(color.dim(`  Preset: ${bundle.architectonic.preset}`));
  console.log(color.dim(`  Workframe cell: ${bundle.deployment.workframe_install ? 'requested' : 'not requested'}`));
  if (!preflight.ok) console.log(color.red('\n  Target is not empty. Choose a new --target path.'));
  console.log(color.yellow(`\n  To instantiate:\n  workframe apply --execute --target="${bundle.architectonic.target_root}" --approval="${approvalPhrase}" plus your begin flags.\n`));
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--version') || args.includes('-v')) {
    console.log(VERSION);
    return;
  }

  const command = args.find((arg) => !arg.startsWith('-')) || 'status';
  const json = args.includes('--json');
  const noTest = args.includes('--no-test') || json || !process.stdin.isTTY;

  if (['help', '--help', '-h'].includes(command)) {
    help();
    return;
  }
  if (['version', '--version', '-v'].includes(command)) {
    console.log(VERSION);
    return;
  }

  if (command === 'begin') return cmdBegin(args);
  if (command === 'capabilities') return cmdCapabilities(args);
  if (command === 'verify') return cmdVerify(args);
  if (command === 'draft') return cmdDraft(args);
  if (command === 'plan') return cmdPlan(args);
  if (command === 'apply') return cmdApply(args);
  if (command === 'origin') return cmdOrigin(args);

  if (command !== 'status') {
    console.error(`Unknown command: ${command}`);
    help();
    process.exitCode = 1;
    return;
  }

  const report = collectStatus(VERSION);
  if (json) {
    console.log(JSON.stringify(report, null, 2));
    return;
  }

  printStatus(report);
  if (!noTest) await askForLegacyTest(report);
}

await main();
