# Program status — Workframe v0.1.12

**Date:** 2026-07-08 (supersedes 2026-07-06 audit)
**Package version:** 0.1.12 ([`docs/VERSION.md`](../VERSION.md))
**Backlog source:** [`backlog.json`](backlog.json) — **verify artifacts before trusting status**
**Orchestration:** [`orchestration.md`](orchestration.md) · **Active plan:** [`handoffs/gate-run-2026-07-08.md`](handoffs/gate-run-2026-07-08.md)

---

## Executive summary

| Metric | Value |
|--------|-------|
| Backlog items | 50 (29 done · 8 partial · 2 todo · 11 deferred) |
| **Stage A** (release-truth) | **Complete** |
| **Stage B** (decompose) | **In flight** — WF-037 done; WF-032/035/036 partial |
| **Stage C** (secure multi-user) | **Done except WF-017** (VPS + backup/restore evidence) |
| **Stage D** (authority + ledger) | **Nearly done** — WF-007/016/NS-P1/NS-P2 partial, all with narrow verified gaps |
| **Stage E+** | **STOP** — 11 deferred items; do not start |

**`ledger-next` pick (2026-07-08):** `WF-032` (Stage B) — server.py 12,144 lines / 318 top-level defs; ~30 modules already extracted; target residual <3k.

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

WF-001…006, WF-018…022, WF-031, WF-033, WF-034, WF-038 — all `done`, evidence scripts green at last matrix. No open items.

### Stage B — decompose 🔄 IN FLIGHT

| ID | Title | Status | Evidence / remaining gap |
|----|-------|--------|--------------------------|
| WF-037 | Declarative route registry | **done** | `route_registry.py`; `test_route_registry.py` audits all 62 patterns (2026-07-07); no `/api` if-chains |
| WF-032 | Split server.py monolith | **partial** | 12,144 lines / 318 defs remain (item summary says ~20k — stale, refresh with next extraction). ~30 modules extracted incl. `chat_stream`, `hermes_profiles`, `profile_gateway`, `model_surface`, `provider_bootstrap`, `db_schema`, `auth_gate`, `rooms`, `kanban_cron`, `activity_feed`, `crew_registry`, `health_monitor`, `snapshot_feed`, `doctor_runtime`, `api_meta`, `run_ledger`, `run_surface_wiring`. Remaining dense zones: credential/provider bindings + oauth/mention helpers (L2000–8000), runtime tokens (L10000–12000), handler shell |
| WF-035 | Exception hygiene (auth/vault) | **partial** | `_log_handler_error` on auth/vault/provider-sync paths (07-06); `test_exception_hygiene.py` exists. Verify acceptance → likely flip. 73 broad excepts remain in server.py but are out of acceptance scope |
| WF-036 | Frontend decomposition | **partial** | Cosmetic slice active in UI lane. Functional slice remains: `ConciergeFlow.tsx`/`HermesSessionContext.tsx` splits, provider-label unification, no silent openrouter default (badge + connectError already fixed) |

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

### Stage D — authority + ledger 🟡 NEARLY DONE

| ID | Title | Status | Evidence / remaining gap |
|----|-------|--------|--------------------------|
| WF-039 | Domain model package | **done** | `domain/`, `test_domain_entities.py` |
| WF-NS-P0 | Vocabulary lock | **done** | glossary + domain entities |
| WF-010 | SurfaceContractGate | **done** | `specs/WF-010/spec.md` |
| WF-009 | RunAuthorityGate | **done** | `run_authority.py` + tests |
| WF-008 | Mutation-free doctor | **done** | `workframe doctor --json` |
| WF-007 | CellAuthorityGate | **partial** | `cell_authority.py` + tests green; `evaluate_open` wired in `updates.apply_update`; CLI wire deferred to WF-014. Gap: confirm connect/adopt coverage or evidence they don't ship in wedge |
| WF-016 | Funding beyond BYOK | **partial** | Payer enforced (`test_run_authority.py`); `run_line_items` table exists. Gap: receipt per run (amounts stay deferred) |
| WF-NS-P1 | Harden Hermes stack | **partial** | Vault + proxy + leases + supervisor shipped; WF-011 negatives done. Gap: explicit SECURE_MODE Docker-socket boundary test |
| WF-NS-P2 | Run ledger tables | **partial → near flip** | Tables + all six surfaces record (chat/mention/kanban/cron/slash/webhook — verified 2026-07-08; `test_run_ledger.py`, `test_run_surface_wiring.py` green); activity panel reads `run_events`. Gap: DM-turn run evidence (DMs are rooms → chat surface), then flip |

### Stage E+ — STOP 🛑

Deferred (11): WF-013, WF-014, WF-015, WF-029, WF-030, WF-NS-P3…P8.
Meta todo: WF-SK-001 (spec-kit, not gating). WF-012 is **todo but in scope** (Wave 3 — release identity, fixes the `ui_bundle_identity` fail class).

---

## Verify matrix

**Latest full matrix:** 2026-07-06 @ `9a06d88` — 16 pass / 1 fail / 2 skip (`operations/release-evidence/runs/latest-verify-matrix.json`). Fail: `package-install-evidence --skip-prep` → `ui_bundle_identity` (stale packed UI; run sync+bundle prep). **Stale — Wave 0 refreshes at HEAD with prep.**

Spot checks this audit (2026-07-08):

| Command | Result |
|---------|--------|
| `node scripts/workframe/ledger-next.mjs` | WF-032 [P1] partial (Stage B) |
| `python test_run_surface_wiring.py` | ok |
| `python test_run_ledger.py` | ok |
| `wc -l server.py` | 12,144 |
| grep `RunSurface.` call sites | chat, mention, kanban, cron, slash, webhook all recorded |
| `git status -sb` | main in sync with origin; dirty tree = UI lane WIP + 2 stray backend fixes (Wave 0 commits them) |

---

## Known drift (fix in Wave 0 / with items)

| Artifact | Drift | Correct truth |
|----------|-------|---------------|
| `backlog.json` WF-032 summary | "~20k lines / 841 KB / 626 defs" | 12,144 lines / 318 defs — refresh with next extraction commit |
| [`now.md`](now.md) | package 0.1.11; egress broker "planned"; run ledger "minimal hooks" | 0.1.12; WF-025 done; six surfaces record runs |
| [`backlog.md`](backlog.md) audit table | pointer only, statuses stale | `backlog.json` + this doc |
| Working tree | `create-workframe.js` `/compose` mount fix + `install-gate.ps1` build guard uncommitted | Commit surgically (G0.1) |

---

## Recommended next execution

Follow [`handoffs/gate-run-2026-07-08.md`](handoffs/gate-run-2026-07-08.md) waves in order:

1. **Wave 0** — commit stray fixes, refresh verify matrix with prep, branch/stash hygiene.
2. **Wave 1** — flip WF-NS-P2, WF-NS-P1, WF-007, WF-035 after closing their narrow verified gaps.
3. **Wave 2** — WF-032 extractions to <3k residual (bulk of the run).
4. **Wave 3** — WF-012 build-stamp identity; WF-016 receipt slice.
5. **Wave 4** — WF-017 VPS + backup/restore evidence (operator-assisted).
6. **Wave 5** — WF-036 functional slice.

Stop at the E gate. Do not start deferred items.

---

## Related

- Active plan: [`handoffs/gate-run-2026-07-08.md`](handoffs/gate-run-2026-07-08.md)
- Human backlog map: [`backlog.md`](backlog.md) (pointer only — not authoritative)
- PM harness: [`operations/pm/README.md`](../../operations/pm/README.md)
- Operator log: [`operations/log.md`](../../operations/log.md)
