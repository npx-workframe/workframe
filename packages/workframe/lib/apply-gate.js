import { createHash } from 'node:crypto';
import path from 'node:path';
import { buildArchitectonicPlan, buildDeploymentPlan } from './plan.js';
import { collectStatus } from './discovery.js';
import { buildConstitutionalDraft } from './mirror.js';

export function buildApplyBundle(draft, statusReport, options = {}) {
  const architectonic = buildArchitectonicPlan(draft, options);
  const deployment = buildDeploymentPlan(draft, statusReport, architectonic);
  const bundle = {
    schema_version: '0.1',
    mode: 'apply_bundle',
    architectonic,
    deployment,
    mutations_preview: [
      { type: 'architectonic_init', target: architectonic.target_root, preset: architectonic.preset },
      { type: 'organization_write', target: path.join(architectonic.target_root, 'organization') },
    ],
  };

  if (deployment.workframe_install) {
    bundle.mutations_preview.push({
      type: 'create_workframe',
      target: path.join(architectonic.target_root, 'workframe-cell'),
    });
    bundle.mutations_preview.push({ type: 'link_kb_to_files', target: 'Files/organization' });
  }

  bundle.plan_hash = hashBundle(bundle);
  return bundle;
}

export function hashBundle(bundle) {
  const stable = {
    architectonic: {
      target_root: bundle.architectonic.target_root,
      preset: bundle.architectonic.preset,
      entity_name: bundle.architectonic.entity_name,
    },
    deployment: {
      workframe_install: bundle.deployment.workframe_install,
      recommendation: bundle.deployment.recommendation,
    },
  };
  return createHash('sha256').update(JSON.stringify(stable)).digest('hex').slice(0, 16);
}

export function bundleFromSession({ mirror, draft, version, targetRoot }) {
  const report = collectStatus(version);
  return buildApplyBundle(draft, report, { targetRoot });
}

export function evaluateApplyGate({ bundle, approvalText, execute = false }) {
  const planHash = bundle.plan_hash || hashBundle(bundle);
  const normalized = String(approvalText || '').trim().toLowerCase();
  const approved = normalized === `approve plan ${planHash}`;

  return {
    schema_version: '0.1',
    mode: execute ? 'apply_execute' : 'apply_preview',
    plan_hash: planHash,
    approved,
    real_mutations_enabled: execute,
    message: approved
      ? (execute ? 'Approval accepted. Executing apply bundle.' : `Dry-run approved. Re-run with --execute and --approval="approve plan ${planHash}"`)
      : `Approval required. Say exactly: approve plan ${planHash}`,
    approval_phrase: `approve plan ${planHash}`,
    mutations: [],
  };
}
