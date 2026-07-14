# Backlog synthesis

**Machine source of truth:** [`backlog.json`](backlog.json) (schema: [`backlog.schema.json`](backlog.schema.json))

**Program status (verified 2026-07-12):** [`program-status.md`](program-status.md) — stage A→D checklist, backlog reconciliation, verify matrix. Read that before this file; `backlog.json` is the machine queue and source of item status.

This file is a human wave map. Agents and CI should read/write `backlog.json`; humans skim here.

## Standalone Workframe CLI campaign

The bounded Socratic CLI campaign is defined in [`specs/WF-CLI-001/spec.md`](specs/WF-CLI-001/spec.md). Independent review returned the first slice to **todo** with exact syntax, consent, credential-wording, authority-boundary, EOF, and CI failures recorded in that spec. `WF-CLI-002` remains blocked. Work remains confined to `packages/workframe/**`; no package has been published and no existing installation has been changed.

Planned sequence: truthful capability graph → bounded inference session → Socratic entity/goal mirror → Architectonic constitutional draft → non-destructive setup reconciliation → deployment dry run → packed cross-platform evidence.

## Waves (execution order)

| Wave | Focus | Active items |
|------|--------|--------------|
| **release-truth** | PackageTruthGate, version parity, evidence JSON, docs-claim gate | WF-001 … WF-006, WF-018 … WF-022 |
| **authority** | CellAuthority, RunAuthority, surfaces, supervisor tests | WF-007 … WF-011 |
| **broker** | Forced egress, broker extract, audit events, lease tests | WF-023 ✓, WF-024 ✓, WF-025 … WF-028 |
| **run-ledger** | runs / run_events / receipt line items | WF-NS-P2, WF-009, WF-016 — **done**; billing amounts remain deferred |
| **adapter** | Identity seam, runtime candidates, second harness, standalone Socratic CLI | WF-013 … WF-015, WF-NS-P4, WF-CLI-001 … WF-CLI-008 |
| **cell** | Manifests, cell metadata, control plane | WF-NS-P5 … WF-NS-P7 |
| **marketplace** | After ledger stable | WF-NS-P8 |
| **meta** | Vocabulary, spec-kit adoption | WF-NS-P0, WF-SK-001 |

## Seventeen consolidated audit findings (25-audit)

| ID | Finding | Backlog | Status |
|----|---------|---------|--------|
| P0-1 | Version agreement | WF-001, WF-022 | **done** |
| P0-2 | PackageTruthGate | WF-002, WF-021 | **done** |
| P0-3 | Split evidence model | WF-003, WF-018 | **done** |
| P0-4 | Empty-target-only claim | WF-004 | **done** |
| P0-5 | Local gates not silent | WF-005 | **done** |
| P0-6 | Docs-claim gate | WF-006 | **done** |
| P1-7 | CellAuthorityGate | WF-007 | **done** |
| P1-8 | Mutation-free doctor | WF-008 | **done** |
| P1-9 | RunAuthorityGate | WF-009 | **done** |
| P1-10 | SurfaceContractGate | WF-010 | **done** |
| P1-11 | Supervisor negative tests | WF-011 | **done** |
| P1-12 | UI/package parity identity | WF-012 | **done** |
| P2-13 | AgentIdentity seam | WF-013 | deferred |
| P2-14 | RuntimeBinding candidates | WF-014 | deferred |
| P2-15 | Second runtime adapter | WF-015 | deferred |
| P2-16 | Funding beyond BYOK | WF-016 | **done** (amounts null) |
| P2-17 | Public/VPS hardening | WF-017 | partial |

## North-star phases (52-page brief)

| Phase | Epic ID | Title | Status |
|-------|---------|-------|--------|
| 0 | WF-NS-P0 | Vocabulary lock | **done** |
| 1 | WF-NS-P1 | Harden Hermes stack | **done** |
| 2 | WF-NS-P2 | Run ledger tables | **done** |
| 3 | WF-NS-P3 | Tool brokers | deferred |
| 4 | WF-NS-P4 | Adapter seam | deferred |
| 5 | WF-NS-P5 | File manifests | deferred |
| 6 | WF-NS-P6 | Cell productization | deferred |
| 7 | WF-NS-P7 | Control plane | deferred |
| 8 | WF-NS-P8 | Marketplace | deferred |

Full prose: [strategy brief](../strategy/workframe_v0_1_1_docs/chapters/12-12-roadmap.md).

## Audit 0027 (Agent Vault)

| Task | ID | Status |
|------|-----|--------|
| Egress doctrine docs | WF-023 | **done** |
| Deploy verify reporting | WF-024 | **done** |
| Forced broker enforcement | WF-025 | todo |
| Broker layer extract | WF-026 | todo |
| Broker audit events | WF-027 | todo |
| Lease test matrix | WF-028 | todo |
| Non-LLM brokers | WF-029 | deferred |
| Agent Vault spike | WF-030 | deferred |

## Living-audit archive

Twenty-seven planning files under [`archive/planning/living-audit/`](../../archive/planning/living-audit/) informed the seventeen findings. They remain linked evidence — not duplicate backlog rows. See [audits.md](audits.md).

## Next agent action

```bash
node scripts/workframe/ledger-next.mjs
node scripts/workframe/ledger-next.mjs --role reviewer
```

See [automation.md](automation.md).
