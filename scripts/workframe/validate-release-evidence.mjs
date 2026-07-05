#!/usr/bin/env node
/**
 * Validate release evidence example fixtures against schema contracts.
 * ponytail: structural check on required fields — not full JSON Schema.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '../..');
const examplesDir = join(root, 'operations/release-evidence/examples');

const ENUMS = {
  evidence_type: new Set(['package_install', 'first_run', 'negative_install']),
  decision: new Set(['allow', 'deny', 'needs_user_action']),
  assertion_status: new Set(['asserted', 'not_asserted', 'failed']),
  target_mode: new Set([
    'single_user_local',
    'trusted_team',
    'public_multi_user',
    'negative_test',
  ]),
};

const TYPE_GATE = {
  package_install: 'PackageInstallGate',
  first_run: 'FirstRunGate',
  negative_install: 'NegativeInstallGate',
};

function fail(msg) {
  console.error(`validate-release-evidence: ${msg}`);
  process.exit(1);
}

function requireString(obj, key, file) {
  if (typeof obj[key] !== 'string' || !obj[key].trim()) {
    fail(`${file}: missing or empty ${key}`);
  }
}

function validateCommon(doc, file) {
  requireString(doc, 'schema_version', file);
  if (doc.schema_version !== '0.1') fail(`${file}: schema_version must be 0.1`);

  requireString(doc, 'evidence_type', file);
  if (!ENUMS.evidence_type.has(doc.evidence_type)) {
    fail(`${file}: invalid evidence_type ${doc.evidence_type}`);
  }
  if (doc.gate_name !== TYPE_GATE[doc.evidence_type]) {
    fail(`${file}: gate_name must be ${TYPE_GATE[doc.evidence_type]}`);
  }

  for (const key of [
    'scenario_id',
    'git_ref',
    'package_name',
    'package_version',
    'target_mode',
    'decision',
    'decision_reason',
    'timestamp',
  ]) {
    requireString(doc, key, file);
  }

  if (doc.package_name !== 'create-workframe') {
    fail(`${file}: package_name must be create-workframe`);
  }
  if (!ENUMS.decision.has(doc.decision)) {
    fail(`${file}: invalid decision`);
  }
  if (!ENUMS.target_mode.has(doc.target_mode)) {
    fail(`${file}: invalid target_mode`);
  }

  if (!Array.isArray(doc.step_assertions) || doc.step_assertions.length < 1) {
    fail(`${file}: step_assertions required`);
  }
  for (const step of doc.step_assertions) {
    if (!step.id || !ENUMS.assertion_status.has(step.status)) {
      fail(`${file}: invalid step_assertion`);
    }
  }
}

function validatePackageInstall(doc, file) {
  requireString(doc, 'packed_artifact_digest', file);
}

function validateNegativeInstall(doc, file) {
  if (doc.target_mode !== 'negative_test') {
    fail(`${file}: negative_install requires target_mode negative_test`);
  }
  if (!Array.isArray(doc.cases) || doc.cases.length < 1) {
    fail(`${file}: cases required`);
  }
  for (const c of doc.cases) {
    if (!c.id || !ENUMS.decision.has(c.decision)) fail(`${file}: invalid case`);
    if (c.mutation_observed !== false) {
      fail(`${file}: case ${c.id} must have mutation_observed false`);
    }
  }
}

const files = readdirSync(examplesDir).filter((f) => f.endsWith('.example.json'));
if (!files.length) fail('no example fixtures found');

for (const file of files) {
  const doc = JSON.parse(readFileSync(join(examplesDir, file), 'utf8'));
  validateCommon(doc, file);
  if (doc.evidence_type === 'package_install') validatePackageInstall(doc, file);
  if (doc.evidence_type === 'negative_install') validateNegativeInstall(doc, file);
  console.log(`  ok ${file}`);
}

console.log(`validate-release-evidence: OK (${files.length} fixtures)`);
