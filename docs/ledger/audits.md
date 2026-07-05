# Audit registry

Point-in-time reviews and planning audits. Update **status** when code or docs close a finding.

## Numbered audits (`docs/audits/`)

| ID | Title | Status | Key finding |
|----|-------|--------|-------------|
| [0027](../audits/0027-agent-vault-comparison.md) | Agent Vault comparison | **partial** | Vault + leases + LLM proxy align with industry; **forced egress broker** still planned |

## Living audit (`docs/living-audit/`)

Convergence planning toward the Workframe cell (v0.1.x → v0.2). Indexed below; full prose stays in place.

### Synthesis

| Doc | Role | Status |
|-----|------|--------|
| [README](../living-audit/README.md) | Index | archive index |
| [25-audit](../living-audit/25-audit.md) | Consolidated living audit | planning |
| [final-convergence-synthesis](../living-audit/final-convergence-synthesis.md) | Roadmap compression | planning |
| [current-code-proof-and-forward-plan](../living-audit/current-code-proof-and-forward-plan.md) | Code-grounded forward plan | planning |
| [package-truth-gate](../living-audit/package-truth-gate.md) | Release gate memo | **active** |
| [release-readiness](../living-audit/release-readiness.md) | Blockers | planning |

### Installer & runtime

| Doc | Topic |
|-----|-------|
| [first-run-wizard](../living-audit/first-run-wizard.md) | Wizard convergence |
| [deployment-order](../living-audit/deployment-order.md) | Mode selection |
| [runtime-detection-map](../living-audit/runtime-detection-map.md) | Environment detection |
| [existing-runtime-adoption-policy](../living-audit/existing-runtime-adoption-policy.md) | Non-destructive adoption |
| [agent-runtime-config](../living-audit/agent-runtime-config.md) | Profile/provider/runtime model |
| [installer-validation-plan](../living-audit/installer-validation-plan.md) | Journey validation |

### Product surfaces & policy

| Doc | Topic |
|-----|-------|
| [workframe-surface-baseline](../living-audit/workframe-surface-baseline.md) | UI/surface contracts |
| [multi-user-provider-policy](../living-audit/multi-user-provider-policy.md) | BYOK / company-pays |
| [refactor-map](../living-audit/refactor-map.md) | Adapter-first refactor seams |

### Red team (01–12)

| ID | Doc | Theme |
|----|-----|-------|
| RT-01 | [red-team-01-adoption-risk](../living-audit/red-team-01-adoption-risk.md) | Adoption / installer category |
| RT-02 | [red-team-02-detection-privacy](../living-audit/red-team-02-detection-privacy.md) | Detection privacy |
| RT-03 | [red-team-03-agent-runtime-matrix](../living-audit/red-team-03-agent-runtime-matrix.md) | Runtime matrix |
| RT-04 | [red-team-04-refactor-seam-risk](../living-audit/red-team-04-refactor-seam-risk.md) | Adapter seams |
| RT-05 | [red-team-05-release-gate-risk](../living-audit/red-team-05-release-gate-risk.md) | Release gates |
| RT-06 | [red-team-06-validation-matrix-risk](../living-audit/red-team-06-validation-matrix-risk.md) | Evidence inflation |
| RT-07 | [red-team-07-open-update-connect-risk](../living-audit/red-team-07-open-update-connect-risk.md) | Update/connect paths |
| RT-08 | [red-team-08-manifest-authority-risk](../living-audit/red-team-08-manifest-authority-risk.md) | Manifest authority |
| RT-09 | [red-team-09-surface-contract-risk](../living-audit/red-team-09-surface-contract-risk.md) | Surface contracts |
| RT-10 | [red-team-10-funding-authority-risk](../living-audit/red-team-10-funding-authority-risk.md) | Funding authority |
| RT-11 | [red-team-11-gate-theater-risk](../living-audit/red-team-11-gate-theater-risk.md) | Gate theater |
| RT-12 | [red-team-12-evidence-authority-collapse](../living-audit/red-team-12-evidence-authority-collapse.md) | Evidence authority |
| — | [red-team-smoke-test-2026-07-04](../living-audit/red-team-smoke-test-2026-07-04.md) | Smoke test |

## Cross-cutting themes → status

| Theme | Audits | Implementation status |
|-------|--------|------------------------|
| Credential vault + leases | 0027, RT-10 | **shipped** |
| LLM proxy | 0027 | **shipped** |
| Forced egress broker | 0027, security.md | **planned** (verify reports; no network enforcement) |
| Package truth / install-gate | package-truth-gate, RT-05–07 | **partial** |
| Runtime adapters | refactor-map, RT-03–04 | **planned** |
| Run ledger / billing | north-star, RT-10 | **deferred** |

## How to close a row

1. Land code or doc in `main`.
2. Point harness or verify script at the claim.
3. Set status to **shipped** or **partial** with commit/link in [now.md](now.md).
