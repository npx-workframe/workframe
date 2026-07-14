# Program status — Workframe v0.1.19

**Date:** 2026-07-12 (backlog/source reconciliation)
**Package version:** 0.1.19 ([`docs/VERSION.md`](../VERSION.md))
**Backlog source:** [`backlog.json`](backlog.json) — **verify artifacts before trusting status**
**Orchestration:** [`orchestration.md`](orchestration.md) · **Active plan:** [`handoffs/gate-run-2026-07-08.md`](handoffs/gate-run-2026-07-08.md)

---

## Executive summary

| Metric | Value |
|--------|-------|
| Backlog items | 53 (37 done · 1 partial · 1 todo · 14 deferred) |
| **Stage A** (release-truth) | **Complete** |
| **Stage B** (decompose) | **Complete** — WF-032/037/035/036 done |
| **Stage C** (secure multi-user) | **Done except WF-017** (VPS + backup/restore evidence) |
| **Stage D** (authority + ledger) | **Complete** |
| **Stage E+** | **STOP** — 14 deferred items; do not start |

**Next actionable item:** `WF-017` (Stage C) — VPS green run + backup/restore evidence (operator-assisted). The remaining 14 deferred items stay behind the E/F stop line.

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

Deferred (14): WF-013, WF-014, WF-015, WF-029, WF-030, WF-NS-P3…P8, WF-041, WF-042, WF-043.
Meta todo: WF-SK-001 (spec-kit, not gating). WF-012 **done** 2026-07-08 (`4a37685`) — `workframe-build.json` stamp + `/api/meta` package_version/ui_build; `ui_bundle_identity` asserts stamp parity.

---

## Verify matrix

**Current release-candidate evidence:** 2026-07-12 @ `4649e15`, package `0.1.19`. `verify-release-gates.mjs` allows installer UI bundle, dogfood install gate, first-run evidence, and negative-install evidence. The authenticated dogfood browser smoke returned `WORKFRAME_OK — ABX` through the supported `gpt-5.4-mini` Codex profile. npm publication remains blocked by owner authentication (`npm whoami` → 401), and the three requested domains have neither DNS records nor Caddy routes.

Spot checks this audit (2026-07-08 @ `fb0ca10`):

| Command | Result |
|---------|--------|
| `node scripts/workframe/ledger-next.mjs` | `WF-017` partial (Stage C) |
| `python test_run_surface_wiring.py` | ok |
| `python test_run_ledger.py` | ok |
| `server.py` line count | 2,626 |
| grep `RunSurface.` call sites | chat, mention, kanban, cron, slash, webhook all recorded |
| `git status -sb` | main **ahead 38** of origin; dirty tree = cosmetic UI lane WIP only |

---

## Known drift (fix in Wave 0 / with items)

| Artifact | Drift | Correct truth |
|----------|-------|---------------|
| [`gate-run-2026-07-08.md`](handoffs/gate-run-2026-07-08.md) baseline | historical 12,144-line / 318-def snapshot | current `server.py` is 2,626 lines; backlog is 37 done · 1 partial · 1 todo · 14 deferred |
| [`now.md`](now.md) | WF-016 receipts were described as "in flight" | WF-016 done; receipt per run on all six surfaces |
| [`orchestration.md`](orchestration.md) Stage B row | described decomposition as in flight | Stage B complete; WF-017 is the remaining partial item |
| [`backlog.md`](backlog.md) audit table | pointer only, statuses stale | `backlog.json` + this doc |
| Public publication/deploy | local release gates green | npm owner authentication, DNS, Caddy routes, SMTP/invite setup, and per-cell backup/restore evidence remain operator-assisted gates |

---

## Recommended next execution

Follow [`handoffs/gate-run-2026-07-08.md`](handoffs/gate-run-2026-07-08.md) waves — progress @ `fb0ca10`:

1. **WF-017** — run the public deploy verifier on the reference VPS and complete a tested backup/restore cycle with operator assistance.
2. **Publish 0.1.19** — authenticate npm as package owner, rerun `npm whoami`, then publish through the supported release script.
3. **Provision requested cells** — create DNS for `abx.alanborger.com`, `dev.click.blue`, and `demo.workfra.me`; then use supported install/update paths and complete HTTPS, SMTP/invite, public-deploy, and backup/restore evidence.
4. **Stop** — keep all 14 E/F items deferred; `WF-SK-001` remains a non-gating meta todo.

**Before E stop line:** finish `WF-017`. WF-SK-001 meta may stay open.

Stop at the E gate. Do not start deferred items.

---

## Related

- Active plan: [`handoffs/gate-run-2026-07-08.md`](handoffs/gate-run-2026-07-08.md)
- Human backlog map: [`backlog.md`](backlog.md) (pointer only — not authoritative)
- PM harness: [`operations/pm/README.md`](../../operations/pm/README.md)
- Operator log: [`operations/log.md`](../../operations/log.md)
