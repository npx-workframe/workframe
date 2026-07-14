#!/usr/bin/env node
/**
 * WF-005: release sign-off fails closed when local harness gates lack evidence.
 * ponytail: reads feature_list + package-install evidence; dogfood still needs passes:true after wizard.
 */
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const currentVersion = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8')).version;
const listPath = path.join(root, '.harness', 'feature_list.json');
const packageEvidencePath = path.join(
  root,
  'operations/release-evidence/runs/latest-package-install.json',
);

const data = JSON.parse(fs.readFileSync(listPath, 'utf8'));
const local = data.scenarios.filter((s) => s.owner === 'cursor-local');

function readPackageEvidence() {
  if (!fs.existsSync(packageEvidencePath)) return null;
  try {
    return JSON.parse(fs.readFileSync(packageEvidencePath, 'utf8'));
  } catch {
    return null;
  }
}

function uiBundleSatisfied() {
  const ev = readPackageEvidence();
  if (!ev || ev.decision !== 'allow') return { ok: false, reason: 'missing or denied PackageInstallEvidence' };
  if (ev.package_version !== currentVersion) {
    return { ok: false, reason: `stale PackageInstallEvidence v${ev.package_version || '?'}; current v${currentVersion}` };
  }
  const step = (ev.step_assertions || []).find((a) => a.id === 'ui_bundle_identity');
  if (!step || step.status !== 'asserted') {
    return { ok: false, reason: 'PackageInstallEvidence lacks ui_bundle_identity' };
  }
  return { ok: true, reason: `evidence @ ${ev.git_ref || 'unknown'} v${ev.package_version || '?'}` };
}

const checks = {
  'installer-ui-bundle': () => {
    const ev = uiBundleSatisfied();
    if (ev.ok) return ev;
    return ev.reason.startsWith('stale ')
      ? ev
      : { ok: false, reason: 'run install-gate.ps1 or run-package-install-evidence.mjs --build' };
  },
  'dogfood-install-gate': () => {
    const evPath = path.join(root, 'operations/release-evidence/runs/latest-first-run.json');
    if (fs.existsSync(evPath)) {
      try {
        const ev = JSON.parse(fs.readFileSync(evPath, 'utf8'));
        if (ev.decision === 'allow' && ev.package_version === currentVersion) {
          return { ok: true, reason: `FirstRunEvidence @ ${ev.git_ref || 'unknown'} v${ev.package_version}` };
        }
        if (ev.decision === 'allow') {
          return { ok: false, reason: `stale FirstRunEvidence v${ev.package_version || '?'}; current v${currentVersion}` };
        }
      } catch {
        /* fall through */
      }
    }
    return { ok: false, reason: `regenerate FirstRunEvidence for v${currentVersion}` };
  },
  'first-run-evidence': () => {
    const evPath = path.join(root, 'operations/release-evidence/runs/latest-first-run.json');
    if (fs.existsSync(evPath)) {
      try {
        const ev = JSON.parse(fs.readFileSync(evPath, 'utf8'));
        if (ev.decision === 'allow' && ev.package_version === currentVersion) {
          return { ok: true, reason: `FirstRunEvidence @ ${ev.git_ref || 'unknown'} v${ev.package_version}` };
        }
        if (ev.decision === 'allow') {
          return { ok: false, reason: `stale FirstRunEvidence v${ev.package_version || '?'}; current v${currentVersion}` };
        }
      } catch {
        /* fall through */
      }
    }
    const res = spawnSync(process.execPath, [path.join(root, 'scripts/workframe/run-first-run-evidence.mjs')], {
      encoding: 'utf8',
      cwd: root,
    });
    if (res.status === 0) return { ok: true, reason: 'FirstRunEvidence runner allow' };
    return { ok: false, reason: 'run-first-run-evidence.mjs or dogfood-install-gate passes:true' };
  },
  'negative-install-evidence': () => {
    const evPath = path.join(root, 'operations/release-evidence/runs/latest-negative-install.json');
    if (!fs.existsSync(evPath)) return { ok: false, reason: 'missing NegativeInstallEvidence' };
    try {
      const ev = JSON.parse(fs.readFileSync(evPath, 'utf8'));
      if (ev.decision !== 'allow') return { ok: false, reason: 'NegativeInstallEvidence denied' };
      if (ev.package_version !== currentVersion) {
        return { ok: false, reason: `stale NegativeInstallEvidence v${ev.package_version || '?'}; current v${currentVersion}` };
      }
      return { ok: true, reason: `NegativeInstallEvidence @ ${ev.git_ref || 'unknown'} v${ev.package_version}` };
    } catch {
      return { ok: false, reason: 'invalid NegativeInstallEvidence JSON' };
    }
  },
};

let failed = 0;
console.log('release-gates: checking local harness scenarios…');
for (const [id, fn] of Object.entries(checks)) {
  const { ok, reason } = fn();
  if (ok) {
    console.log(`[allow] ${id} — ${reason}`);
  } else {
    console.error(`[blocked] ${id} — ${reason}`);
    failed++;
  }
}

if (failed) {
  console.error(`release-gates: DENY — ${failed} local gate(s) blocked (CI skips these; publish/sign-off cannot).`);
  process.exit(1);
}
console.log('release-gates: ALLOW — all tracked local gates satisfied.');
