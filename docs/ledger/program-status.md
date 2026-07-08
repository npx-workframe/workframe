# Program status — Workframe v0.1.12

**Date:** 2026-07-08 (supersedes 2026-07-06 audit)
**Package version:** 0.1.12 ([`docs/VERSION.md`](../VERSION.md))
**Backlog source:** [`backlog.json`](backlog.json) — **verify artifacts before trusting status**
**Orchestration:** [`orchestration.md`](orchestration.md) · **Active plan:** [`handoffs/gate-run-2026-07-08.md`](handoffs/gate-run-2026-07-08.md)

---

## Executive summary

| Metric | Value |
|--------|-------|
| Backlog items | 50 (37 done · 1 partial · 1 todo · 11 deferred) |
| **Stage A** (release-truth) | **Complete** |
| **Stage B** (decompose) | **Complete** — WF-032/037/035/036 done |
| **Stage C** (secure multi-user) | **Done except WF-017** (VPS + backup/restore evidence) |
| **Stage D** (authority + ledger) | **Complete** |
| **Stage E+** | **STOP** — 11 deferred items; do not start |

**`ledger-next` pick (2026-07-08):** `WF-017` (Stage C) — VPS green run + backup/restore evidence (operator-assisted).

**Mission:** close every A–D gap, stop at the E gate — ordered waves in [`gate-run-2026-07-08.md`](handoffs/gate-run-2026-07-08.md).

---

## Active constraints (Alan 2026-07-06, lanes clarified 2026-07-07)

1. **Parallel lanes on `main`** — backend lane (API/supervisor/ledger/WF items) and cosmetic UI lane (CSS/themes/tokens only) may share `main` with surgical one-concern commits. See [`handoffs/cosmetic-ui-lane.md`](handoffs/cosmetic-ui-lane.md).
2. **Verify-first** — grep/run evidence before patching; if acceptance met, backlog-only update.
3. **Deferred stop line** — Stage **E+** only: WF-013…015, WF-029/030, WF-NS-P3…P8. Stage D includes WF-NS-P2.
4. **One WF per commit** when possible; no drive-by refactors.

---

## Stage checklist (A → D)

### Stage A — release-truth ✅ COMPLETE

WF-001…006, WF-012, WF-018…022, WF-031, WF-033, WF-034, WF-038 — all `done`, evidence scripts green at last matrix. WF-012 build-stamp (`4a37685`) closes `ui_bundle_identity` stale-bundle class.

### Stage B — decompose ✅ COMPLETE

| ID | Title | Status | Evidence |
|----|-------|--------|----------|
| WF-037 | Declarative route registry | **done** | `route_registry.py` + audit tests |
| WF-032 | Split server.py monolith | **done** | 2,602 lines + `handler_modules/` @ `9538eec` |
| WF-035 | Exception hygiene | **done** | `test_exception_hygiene.py` |
| WF-036 | Frontend decomposition | **done** | ConciergeFlow + HermesSession splits; provider labels; `8085e68` |

### Stage C — secure multi-user ✅ DONE except WF-017

| ID | Title | Status | Evidence / gap |
|----|-------|--------|----------------|
| WF-023/024 | Egress doctrine + deploy reporting | **done** | `security.md`, `verify-public-deploy.sh` |
| WF-026 | Credential broker layer | **done** | `credential_broker.py` |
| WF-027 | Broker audit events | **done** | `broker_audit.py` |
| WF-028 | Lease validation test matrix | **done** | `test_credential_lease_matrix.py` |
| WF-011 | Supervisor negative tests | **done** | package supervisor negatives |
| WF-025 | Force agent egress broker | **done** | compose + iptables |
| WF-017 | Public/VPS hardening evidence | **partial** | `verify-public-deploy.sh` exists; **missing:** green run on reference VPS + tested backup/restore cycle. Gate for first real team cell (operator-assisted — Wave 4) |

### Stage D — authority + ledger ✅ COMPLETE

| ID | Title | Status | Evidence / remaining gap |
|----|-------|--------|--------------------------|
| WF-039 | Domain model package | **done** | `domain/`, `test_domain_entities.py` |
| WF-NS-P0 | Vocabulary lock | **done** | glossary + domain entities |
| WF-010 | SurfaceContractGate | **done** | `specs/WF-010/spec.md` |
| WF-009 | RunAuthorityGate | **done** | `run_authority.py` + tests |
| WF-008 | Mutation-free doctor | **done** | `workframe doctor --json` |
| WF-007 | CellAuthorityGate | **done** | `test_cell_authority.py` + `updates.apply_update` authority wiring; connect/adopt deny by default; CLI deferred WF-014 |
| WF-016 | Funding beyond BYOK | **done** | `b08071a`: receipt per run on all six surfaces (`test_run_ledger.py`, `test_run_surface_wiring.py`); payer enforced (`test_run_authority.py`); `amount_usd` null — billing amounts/pricing deferred Stage E |
| WF-NS-P1 | Harden Hermes stack | **done** | `test_secure_mode_docker_boundary.py` + WF-011 supervisor negatives (2026-07-08) |
| WF-NS-P2 | Run ledger tables | **done** | All six surfaces + DM chat path (`test_run_ledger.py`, `test_run_surface_wiring.py`) — flipped 2026-07-08 |

### Stage E+ — STOP 🛑

Deferred (11): WF-013, WF-014, WF-015, WF-029, WF-030, WF-NS-P3…P8.
Meta todo: WF-SK-001 (spec-kit, not gating). WF-012 **done** 2026-07-08 (`4a37685`) — `workframe-build.json` stamp + `/api/meta` package_version/ui_build; `ui_bundle_identity` asserts stamp parity.

---

## Verify matrix

**Latest package-install evidence:** 2026-07-08 @ `fb0ca10` — `allow` (`run-package-install-evidence.mjs --skip-prep` after bundle; `ui_bundle_identity` via `workframe-build.json` stamp / WF-012). Full matrix still stale @ `9a06d88` — refresh with prep when convenient (G0.2).

Spot checks this audit (2026-07-08 @ `fb0ca10`):

| Command | Result |
|---------|--------|
| `node scripts/workframe/ledger-next.mjs` | WF-032 [P1] partial (Stage B) |
| `python test_run_surface_wiring.py` | ok |
| `python test_run_ledger.py` | ok |
| `wc -l server.py` | 5,107 |
| grep `RunSurface.` call sites | chat, mention, kanban, cron, slash, webhook all recorded |
| `git status -sb` | main **ahead 38** of origin; dirty tree = cosmetic UI lane WIP only |

---

## Known drift (fix in Wave 0 / with items)

| Artifact | Drift | Correct truth |
|----------|-------|---------------|
| [`gate-run-2026-07-08.md`](handoffs/gate-run-2026-07-08.md) baseline | 12,144 lines / 318 defs; 29 done · 8 partial | 5,107 lines / 78 defs; 35 done · 3 partial — Waves 1+3 largely closed |
| [`now.md`](now.md) | WF-016 receipts "in flight" | WF-016 done; receipt per run on all six surfaces |
| [`orchestration.md`](orchestration.md) Stage B row | "12.1k → <3k" | 5.1k → <3k; handler shell extractions in flight |
| [`backlog.md`](backlog.md) audit table | pointer only, statuses stale | `backlog.json` + this doc |
| Verify matrix | stale @ `9a06d88` | Refresh at HEAD with sync+bundle prep (G0.2) |

---

## Recommended next execution

Follow [`handoffs/gate-run-2026-07-08.md`](handoffs/gate-run-2026-07-08.md) waves — progress @ `fb0ca10`:

1. **Wave 0** — refresh verify matrix with prep (G0.2); branch/stash hygiene.
2. **Wave 1** — ✅ closed (WF-NS-P2, WF-NS-P1, WF-007, WF-035 all `done`).
3. **Wave 2** — **in flight** — WF-032: 12.1k → 5.1k; continue handler shell + remaining extractions to <3k.
4. **Wave 3** — ✅ closed (WF-012 `4a37685`, WF-016 `b08071a`).
5. **Wave 4** — WF-017 VPS + backup/restore evidence (operator-assisted).
6. **Wave 5** — **partial** — ConciergeFlow split done (`e3b15e6`); HermesSessionContext + provider labels remain.

**Before E stop line:** finish Stage B (WF-032, WF-036) + Stage C (WF-017). WF-SK-001 meta may stay open.

Stop at the E gate. Do not start deferred items.

---

## Related

- Active plan: [`handoffs/gate-run-2026-07-08.md`](handoffs/gate-run-2026-07-08.md)
- Human backlog map: [`backlog.md`](backlog.md) (pointer only — not authoritative)
- PM harness: [`operations/pm/README.md`](../../operations/pm/README.md)
- Operator log: [`operations/log.md`](../../operations/log.md)
