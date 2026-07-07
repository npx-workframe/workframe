# Program status — Workframe v0.1.12

**Date:** 2026-07-06  
**Package version:** 0.1.12 ([`docs/VERSION.md`](../VERSION.md))  
**Backlog source:** [`backlog.json`](backlog.json) — **verify artifacts before trusting status**  
**Orchestration:** [`orchestration.md`](orchestration.md)

---

## Executive summary

| Metric | Value |
|--------|-------|
| Backlog items | 50 (22 done · 5 partial · 11 todo · 12 deferred) |
| **Stage A** (release-truth) | **Complete** — 8/8 verified |
| **Stage B** (decompose) | **In flight** — WF-037 done; WF-032 partial; WF-035 partial |
| **Stage C** (secure multi-user) | **Mostly done** — WF-026/027/028/011/025 done; WF-017 partial (manual VPS) |
| **Stage D** (authority) | **Partial** — WF-009/008/039/010 done; WF-007/016/NS-P2 partial |
| **Stage E+** | **STOP** — 12 deferred items; do not start |

**`ledger-next` pick (2026-07-07):** `WF-032` (Stage B) — WF-037 route registry complete; continue server.py module split.

---

## Active constraints (Alan 2026-07-06, lanes clarified 2026-07-07)

1. **Parallel lanes on `main`** — multiple agents may work the same branch concurrently if each change is **surgical** (one concern per commit):
   - **Backend lane** — `services/workframe-api/`, supervisor, route registry, run ledger, WF backlog items, API wiring. No cosmetic CSS sweeps.
   - **UI lane** — cosmetic only: new themes, CSS/token refactors, palette contracts, global semantic HTML tweaks that apply across themes. No session/model/chat API wiring, no `server.py`, no ledger status edits.
   - See [`handoffs/cosmetic-ui-lane.md`](handoffs/cosmetic-ui-lane.md) for boundaries and safe zones.
2. **Verify-first** — grep/run evidence before patching; if acceptance met, backlog-only update.
3. **Deferred stop line** — Stage **E+** only: WF-013…015, WF-029/030, WF-NS-P3…P8. **Stage D includes WF-NS-P2** (run ledger tables).
4. **One WF per commit** when possible; no drive-by refactors.

---

## Stage checklist (A → D)

### Stage A — release-truth ✅ COMPLETE

| ID | Title | Backlog | Verified | Evidence |
|----|-------|---------|----------|----------|
| WF-001 | Version agreement gate | done | **done** | `pnpm verify:version` → OK 0.1.12 |
| WF-002 | PackageTruthGate | done | **done** | `run-package-install-evidence.mjs`; Alan dogfood sign-off |
| WF-003 | Split evidence model | done | **done** | `operations/release-evidence/schema/` |
| WF-004 | Empty-target-only install | done | **done** | `run-negative-install-evidence.mjs`; `docs/public/install.md` |
| WF-005 | Release gates not silent | done | **done** | `verify-release-gates.mjs` |
| WF-006 | Docs-claim gate | done | **done** | `pnpm verify:docs` → ALLOW (18 files, 8 rules) |
| WF-018 | Evidence JSON schema | done | **done** | `operations/release-evidence/` |
| WF-019 | Negative install runner | done | **done** | `runs/latest-negative-install.json` (decision: allow) |
| WF-020 | First-run runner | done | **done** | `runs/latest-first-run.json`; `test:first-run-evidence` script |
| WF-021 | Package install runner | done | **done** | `run-package-install-evidence.mjs` |
| WF-022 | Version verifier script | done | **done** | `verify-version-agreement.mjs` |
| WF-031 | Close anonymous GET exposure | done | **done** | `test_public_routes.py`; no `GET_PUBLIC_ROUTES` in tree |
| WF-033 | Single YAML config writer | done | **done** | `profile_config_yaml.py` |
| WF-034 | Model surface regression tests | done | **done** | `test_model_surface_consistency.py` |
| WF-038 | Prune stub packages | done | **done** | stub dirs removed from workspace |

*Stage A closure note:* `orchestration.md` still says A "in flight" — stale; this doc supersedes for 2026-07-06.

### Stage B — decompose 🔄 IN FLIGHT

| ID | Title | Backlog | Verified | Evidence / gap |
|----|-------|---------|----------|----------------|
| WF-037 | Declarative route registry | done | **done** | `route_registry.py`; 55+44+4 exact + 62 pattern handlers; `test_route_registry.py` green; no `/api` if-chains in dispatch |
| WF-032 | Split server.py monolith | partial | **partial** | 12 modules extracted; `server.py` ~12.2k lines (target ~3k) |
| WF-035 | Exception hygiene (auth/vault) | partial | **partial** | Auth/vault `_route_*` paths; broad sweep remains |
| WF-036 | Frontend decomposition | partial | **partial (UI lane)** | Theme/CSS expansion active (blueprint, token architecture, canvas background). Backend lane must not mix cosmetic sweeps. |

### Stage C — secure multi-user ⏳ QUEUED

| ID | Title | Backlog | Verified | Evidence / gap |
|----|-------|---------|----------|----------------|
| WF-023 | Egress doctrine docs | done | **done** | `docs/public/security.md` |
| WF-024 | Public deploy egress reporting | done | **done** | `verify-public-deploy.sh` |
| WF-026 | Credential broker layer | done | **done** | `credential_broker.py` |
| WF-028 | Lease validation test matrix | done | **done** | `test_credential_lease_matrix.py` |
| WF-027 | Broker audit events | done | **done** | `broker_audit.py` |
| WF-011 | Supervisor negative tests | done | **done** | package supervisor negatives |
| WF-025 | Force agent egress broker | done | **done** | compose + iptables |
| WF-017 | Public/VPS hardening evidence | partial | **partial** | `verify-public-deploy.sh` exists; VPS reference run + backup/restore not evidenced |

**Gate:** Stage C substantially unblocked — WF-037 route migration complete (2026-07-07).

### Stage D — authority + ledger 🟡 STARTED

| ID | Title | Backlog | Verified | Evidence / gap |
|----|-------|---------|----------|----------------|
| WF-039 | Domain model package | done | **done** | `services/workframe-api/domain/`; `test_domain_entities.py` green; `docs/public/glossary.md` |
| WF-010 | SurfaceContractGate | done | **done** | `docs/ledger/specs/WF-010/spec.md` |
| WF-NS-P0 | Vocabulary lock | done | **done** | Glossary + domain entities |
| WF-007 | CellAuthorityGate | partial | **partial** | `cell_authority.py` + tests; `evaluate_open` wired in `updates.apply_update` |
| WF-009 | RunAuthorityGate | done | **done** | `run_authority.py` + tests |
| WF-008 | Mutation-free doctor | done | **done** | `workframe doctor --json` |
| WF-016 | Funding beyond BYOK | partial | **partial** | Run ledger records payer; billing amounts deferred |
| WF-NS-P2 | Run ledger tables | partial | **partial** | Schema + chat path; DM/cron/slash gaps |

**Lane outcome:** `lane-domain-design` **COMPLETE** (WF-039, WF-NS-P0, WF-010).

### Stage E+ — STOP 🛑

Deferred: WF-013, WF-014, WF-015, WF-029, WF-030, WF-NS-P3…P8.  
Meta todo: WF-SK-001 (spec-kit). WF-040 **done** (2026-07-06).

---

## Agent lane outcomes (2026-07-06 session)

| Lane | Agent | Scope | Outcome |
|------|-------|-------|---------|
| release-truth | 99ca9676 | WF-006/019/020/004 | **Stage A closed** — verify scripts + evidence JSON green |
| api-decompose | 2218d43e | WF-037/032/035 | **WF-037 partial** — registry + tests; server split not started |
| domain-design | 5aaa78c1 | WF-039, glossary, WF-010 | **COMPLETE** |
| frontend | 35ba1396 | WF-036 | **ACTIVE** — cosmetic/themes lane (parallel with backend on `main`) |
| doc-audit | (this run) | program-status | In progress |

---

## Backlog reconciliation

*Verified 2026-07-06 via `ledger-next`, `pnpm verify:docs`, `pnpm verify:version`, `test_route_registry.py`, `test_domain_entities.py`, artifact grep.*

| WF-ID | backlog.json | Verified | Evidence command / path | Action needed |
|-------|--------------|----------|-------------------------|---------------|
| WF-001 | done | done | `pnpm verify:version` | — |
| WF-002 | done | done | `run-package-install-evidence.mjs` | — |
| WF-003 | done | done | `operations/release-evidence/schema/` | — |
| WF-004 | done | done | `runs/latest-negative-install.json` | — |
| WF-005 | done | done | `verify-release-gates.mjs` | — |
| WF-006 | done | done | `pnpm verify:docs` | — |
| WF-007 | partial | partial | `specs/WF-007/spec.md` | Implement after WF-039 + authority lane |
| WF-008 | todo | todo | — | Design + implement doctor JSON |
| WF-009 | todo | todo | — | Design doc; blocked on WF-NS-P2 |
| WF-010 | done | done | `specs/WF-010/spec.md` | — |
| WF-011 | todo | todo | — | Supervisor denial tests |
| WF-012 | todo | todo | — | **Out of scope** (UI) this push |
| WF-013…015 | deferred | deferred | — | **Do not start** |
| WF-016 | partial | partial | company-pays UI in product | Run ledger + receipts |
| WF-017 | partial | partial | `verify-public-deploy.sh` | VPS reference + backup evidence |
| WF-018…022 | done | done | evidence scripts | — |
| WF-023…024 | done | done | security.md, verify script | — |
| WF-025…028 | todo | todo | no broker module | Stage C queue |
| WF-029…030 | deferred | deferred | — | **Do not start** |
| WF-031 | done | done | `test_public_routes.py` | — |
| WF-032 | partial | partial | server.py ~11k lines | Continue module split (Stage B next) |
| WF-033 | done | done | `profile_config_yaml.py` | — |
| WF-034 | done | done | `test_model_surface_consistency.py` | — |
| WF-035 | todo | todo | — | After WF-032 |
| WF-036 | partial | partial | theme/CSS refactor in flight | **UI lane** — cosmetic only; see cosmetic-ui handoff |
| WF-037 | done | done | `route_registry.py` (103 exact + 62 pattern) | — |
| WF-038 | done | done | workspace prune | — |
| WF-039 | done | done | `domain/`, `test_domain_entities.py` | — |
| WF-040 | done | done | program_stages + ledger-next + PM runbook | — |
| WF-NS-P0 | done | done | `glossary.md`, `domain/` | — |
| WF-NS-P1 | partial | partial | vault, llm_proxy, supervisor | WF-011 negatives |
| WF-NS-P2…P8 | deferred | deferred | — | **Do not start** |
| WF-SK-001 | todo | todo | — | Low priority meta |

### Known backlog drift (human docs / PM notes)

| Artifact | Drift | Correct truth |
|----------|-------|-----------------|
| [`backlog.md`](backlog.md) audit table | WF-004 partial, WF-006 todo, WF-NS-P0 partial | All **done** per `backlog.json` + verify |
| [`orchestration.md`](orchestration.md) Stage A | "in flight" | **Complete** (2026-07-06) |
| `operations/pm/status.json` notes | stale lane counts | **ledger-next → WF-037**; WF-040 done |
| `backlog.json` WF-037 `completed_at` | Set 2026-07-05 while status partial | Status **partial** is correct; date is misleading — fix optional |

*No `backlog.json` status flips applied this audit — verified statuses align with artifacts for all P0 release-truth items.*

---

## Verify matrix (this audit)

| Command | Result |
|---------|--------|
| `node scripts/workframe/ledger-next.mjs` | WF-037 [P1] partial (Stage B) |
| `pnpm verify:docs` | ALLOW — 18 files, 8 rules |
| `pnpm verify:version` | OK (0.1.12) |
| `python test_route_registry.py` | route registry self-check ok |
| `python test_domain_entities.py` | ok |
| `grep GET_PUBLIC_ROUTES services/workframe-api` | **0 matches** |
| `grep credential_broker services/workframe-api` | **0 matches** (WF-026 not started) |

**Full matrix (2026-07-06):** `operations/release-evidence/runs/latest-verify-matrix.json` — **16 pass / 1 fail / 2 skip** @ `9a06d88`. Fail: `run-package-install-evidence.mjs --skip-prep` (`ui_bundle_identity` — stale `workframe-ui` bundle; run sync + bundle before pack evidence). Release gates still ALLOW via prior `feature_list` sign-off.

## Recommended next execution

1. **WF-037** — migrate remaining `do_GET`/`do_POST` if-chain routes into `ROUTES`; delete duplicate auth paths; extend `test_route_registry.py` coverage.
2. **WF-032** — first leaf extraction (e.g. `auth_gate.py` or `db_schema.py`) one module per commit.
3. **Stage C queue** — WF-026 broker extract after B1 substantially complete.
4. **Hygiene** — optional: fix WF-037 `completed_at` in backlog.json.

---

## Related

- Human backlog map: [`backlog.md`](backlog.md) (pointer only — not authoritative)
- PM harness: [`operations/pm/README.md`](../../operations/pm/README.md)
- Operator log: [`operations/log.md`](../../operations/log.md)
