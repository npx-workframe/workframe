import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { buildFirstMirror, buildConstitutionalDraft } from '../lib/mirror.js';
import { buildCapabilityGraph, listEligibleVerificationCandidates } from '../lib/capability-graph.js';
import { resolveCandidateSelection } from '../lib/inference-selection.js';
import { collectStatus } from '../lib/discovery.js';
import { buildArchitectonicPlan, buildDeploymentPlan } from '../lib/plan.js';
import { buildApplyBundle, evaluateApplyGate } from '../lib/apply-gate.js';
import { writeOrganizationFromDraft } from '../lib/organization-write.js';
import os from 'node:os';
import fs from 'node:fs';
import { runBegin } from '../lib/begin.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const CLI = path.join(ROOT, 'bin', 'workframe.js');

test('begin builds memory-only mirror from flags', async () => {
  const { mirror } = await runBegin({
    seed: {
      human: 'Alan',
      entity: 'AB Studio',
      purpose: 'Ship Workframe',
      why: 'Repeatable agent workspaces',
      success: 'Four stable cells',
      constraints: 'No silent overwrite',
      execution_surface: 'Workframe cell with Hermes',
    },
    ask: null,
  });
  assert.equal(mirror.mode, 'memory_only_mirror');
  assert.equal(mirror.fields.human.value, 'Alan');
  assert.equal(mirror.network_calls, 0);
  assert.equal(mirror.unresolved_questions.length, 0);
});

test('inference selection rejects descriptive mentions', () => {
  const candidates = [
    { id: 'claude-runtime', label: 'Claude' },
    { id: 'openrouter-api', label: 'OpenRouter' },
  ];
  const result = resolveCandidateSelection('I do not trust OpenRouter', candidates);
  assert.equal(result.status, 'unresolved');
});

test('inference selection accepts explicit affirmative', () => {
  const candidates = [
    { id: 'codex-runtime', label: 'Codex' },
    { id: 'openrouter-api', label: 'OpenRouter' },
  ];
  const result = resolveCandidateSelection('use codex', candidates);
  assert.equal(result.status, 'selected');
  assert.equal(result.candidate.id, 'codex-runtime');
});

test('capability graph does not auto-select', () => {
  const report = collectStatus('0.3.0');
  const graph = buildCapabilityGraph(report);
  assert.ok(Array.isArray(graph.candidates));
  assert.ok(!('selected' in graph));
});

test('constitutional draft and plans stay dry-run', async () => {
  const { mirror } = await runBegin({
    seed: {
      human: 'Alan',
      entity: 'Studio',
      purpose: 'Knowledge base',
      why: 'Agents',
      success: 'Less hallucination',
      constraints: 'Explicit authority',
      execution_surface: 'Architectonic only',
    },
    ask: null,
  });
  const draft = buildConstitutionalDraft(mirror);
  const report = collectStatus('0.3.0');
  const arch = buildArchitectonicPlan(draft);
  const deploy = buildDeploymentPlan(draft, report, arch);
  assert.equal(arch.dry_run, true);
  assert.equal(deploy.dry_run, true);
  assert.equal(deploy.workframe_install, false);
  assert.deepEqual(arch.mutations, []);
});

test('apply gate requires exact approval phrase', () => {
  const draft = {
    authority_root: { value: 'Alan' },
    entity: { value: 'Studio' },
    purpose: { value: 'KB' },
    execution_surface: { value: 'architectonic only' },
  };
  const report = collectStatus('0.4.0');
  const bundle = buildApplyBundle(draft, report, { targetRoot: path.join(os.tmpdir(), 'wf-test-bundle') });
  const gate = evaluateApplyGate({ bundle, approvalText: 'yes please', execute: false });
  assert.equal(gate.approved, false);
  const ok = evaluateApplyGate({ bundle, approvalText: `approve plan ${bundle.plan_hash}`, execute: false });
  assert.equal(ok.approved, true);
});

test('CLI begin --json smoke', () => {
  const result = spawnSync(process.execPath, [
    CLI,
    'begin',
    '--json',
    '--human=Test',
    '--entity=Entity',
    '--purpose=Purpose',
    '--why=Why',
    '--success=Success',
    '--constraints=None',
    '--execution_surface=Files only',
  ], { encoding: 'utf8' });
  assert.equal(result.status, 0);
  const body = JSON.parse(result.stdout);
  assert.equal(body.mode, 'memory_only_mirror');
});

test('organization write updates scaffold files', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'wf-org-'));
  const org = path.join(tmp, 'organization');
  fs.mkdirSync(org, { recursive: true });
  const template = `---\ntype: project\nstatus: needs-interview\n---\n\n# Project Index\n\n| Project | Purpose | Owner | Canonical sources | Status | Decisions | Open questions |\n| --- | --- | --- | --- | --- | --- | --- |\n`;
  fs.writeFileSync(path.join(org, 'project.md'), template);
  fs.writeFileSync(path.join(org, 'identity.md'), '# Actors\n\n## Humans and organizations\n\n| Actor | Role |\n| --- | --- |\n');
  fs.writeFileSync(path.join(org, 'open-questions.md'), '# Open Questions\n\n| Question | Why | File | Owner | By | Status |\n| --- | --- | --- | --- | --- | --- |\n');
  fs.writeFileSync(path.join(org, 'decisions.md'), '# Decisions\n\n| Date | Decision | Authority | Evidence | Scope | Alt | Revisit |\n| --- | --- | --- | --- | --- | --- | --- |\n');
  const draft = {
    authority_root: { value: 'Alan' },
    entity: { value: 'Test Entity' },
    purpose: { value: 'Test purpose' },
    why: { value: 'Because' },
    success_criteria: { value: 'Done' },
    constraints: { value: 'None' },
    execution_surface: { value: 'files' },
    unresolved_questions: ['extra'],
  };
  writeOrganizationFromDraft(tmp, draft);
  const project = fs.readFileSync(path.join(org, 'project.md'), 'utf8');
  assert.match(project, /Test purpose/);
});

test('CLI capabilities and draft smoke', () => {
  const caps = spawnSync(process.execPath, [CLI, 'capabilities', '--json'], { encoding: 'utf8' });
  assert.equal(caps.status, 0);
  const graph = JSON.parse(caps.stdout);
  assert.ok(graph.candidates);

  const draft = spawnSync(process.execPath, [
    CLI, 'draft', '--json', '--human=A', '--entity=E', '--purpose=P', '--why=W', '--success=S', '--constraints=C', '--execution_surface=none',
  ], { encoding: 'utf8' });
  assert.equal(draft.status, 0);
  assert.equal(JSON.parse(draft.stdout).mode, 'constitutional_draft');
});
