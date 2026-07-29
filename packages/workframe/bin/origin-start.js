import { spawnSync } from 'node:child_process';
import path from 'node:path';
import process from 'node:process';
import readline from 'node:readline/promises';
import { fileURLToPath } from 'node:url';

const BIN_DIR = path.dirname(fileURLToPath(import.meta.url));

export function parseForms(value) {
  if (!value) return [];
  const aliases = new Map([
    ['0', 'none'], ['none', 'none'], ['not yet', 'none'],
    ['1', 'organization'], ['org', 'organization'], ['organization', 'organization'],
    ['2', 'business'], ['biz', 'business'], ['business', 'business'],
    ['3', 'project'], ['proj', 'project'], ['project', 'project'],
  ]);
  const forms = [...new Set(String(value)
    .toLowerCase()
    .split(/[,+]/)
    .map((item) => aliases.get(item.trim()))
    .filter(Boolean))];
  return forms.length > 1 ? forms.filter((form) => form !== 'none') : forms;
}

export function chooseInferencePath(report) {
  const runtimes = Object.fromEntries((report.runtimes || []).map((item) => [item.id, item]));
  const providers = Object.fromEntries((report.providers || []).map((item) => [item.id, item]));
  if (runtimes.codex?.status === 'authenticated') return { kind: 'runtime', id: 'codex', label: runtimes.codex.label };
  if (runtimes.claude?.status === 'verified') return { kind: 'runtime', id: 'claude', label: runtimes.claude.label };
  if (runtimes.hermes?.status === 'verified') return { kind: 'runtime', id: 'hermes', label: runtimes.hermes.label };
  for (const id of ['openrouter', 'openai', 'anthropic', 'google']) {
    if (providers[id]?.status === 'configured') return { kind: 'provider', id, label: providers[id].label };
  }
  return null;
}

export function buildFormationPlan(report, purpose, forms) {
  const nextQuestion = !purpose
    ? 'What are you trying to accomplish, for whom, and what would success look like?'
    : !forms.length
      ? 'What kind of durable thing, if any, should carry this purpose: organization, business, project, or none yet?'
      : 'Which existing sources should be considered before this purpose and structure become durable doctrine?';
  return {
    schema_version: '0.1',
    mode: 'plan_only',
    purpose_statement: purpose || null,
    candidate_forms: forms,
    inference_candidate: chooseInferencePath(report),
    authorization_required: true,
    inspected_paths: [],
    mutations: [],
    next_question: nextQuestion,
  };
}

function readStatus() {
  const result = spawnSync(process.execPath, [path.join(BIN_DIR, 'workframe.js'), 'status', '--json'], {
    encoding: 'utf8',
    windowsHide: true,
  });
  if (result.status !== 0) throw new Error(result.stderr.trim() || 'Workframe status failed.');
  try {
    return JSON.parse(result.stdout);
  } catch {
    throw new Error('Workframe status returned invalid JSON.');
  }
}

function findOption(args, name) {
  const inline = args.find((arg) => arg.startsWith(`${name}=`));
  if (inline) return inline.slice(name.length + 1);
  const index = args.indexOf(name);
  return index >= 0 ? args[index + 1] : undefined;
}

async function askFormation() {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try {
    const purpose = (await rl.question(
      '\nWhat are you trying to accomplish, for whom, and what would success look like?\n> ',
    )).trim();
    if (!purpose) return { purpose: '', forms: [] };
    const answer = await rl.question(
      '\nWhat kind of durable thing, if any, should carry this purpose?\n' +
      '  0. None yet\n  1. Organization\n  2. Business\n  3. Project\n> ',
    );
    return { purpose, forms: parseForms(answer) };
  } finally {
    rl.close();
  }
}

export async function runOriginStart(args = process.argv.slice(2)) {
  const json = args.includes('--json');
  let purpose = (findOption(args, '--purpose') || '').trim();
  let forms = parseForms(findOption(args, '--forms'));
  if (!purpose && process.stdin.isTTY && !json) ({ purpose, forms } = await askFormation());

  const plan = buildFormationPlan(readStatus(), purpose, forms);
  if (json) {
    console.log(JSON.stringify(plan, null, 2));
    return;
  }

  console.log('\nWORKFRAME ORIGIN // FORMATION PREFLIGHT');
  console.log('No files were inspected and nothing was changed.');
  console.log(`Purpose: ${purpose || 'not stated'}`);
  console.log(`Form: ${forms.length ? forms.join(', ') : 'not selected'}`);
  console.log(`Inference: ${plan.inference_candidate?.label ?? 'none detected'}`);
  console.log(`Next: ${plan.next_question}\n`);
}
