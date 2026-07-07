# Orchestration — Workframe program execution

**Owner:** pm-workframe (Cursor)  
**Source of truth:** `git` + `docs/ledger/backlog.json`  
**Updated:** 2026-07-06

## Rules

1. **One WF item per commit** when possible — message prefix `fix|test|refactor|chore(scope): WF-xxx …`
2. **Reversible checkpoints** — each commit must pass `pnpm --filter @workframe/workframe-api typecheck`; no mixed unrelated items
3. **Backlog before code** — set `status: in_progress` when starting; `done` + `completed_at` when merged
4. **Handoff** — use `handoff_steps` on the backlog item; agent reads item id only

## Parallel lanes (2026-07-07)

Multiple agents may share **`main`** when each makes **surgical** commits in its lane.

| Lane | Owner | Scope | Backlog |
|------|-------|-------|---------|
| **Backend** | implementation agent | API, supervisor, route registry, run ledger, WF items, wiring | WF-037 → WF-032 → WF-035 → Stage C/D |
| **UI (cosmetic)** | separate agent / human | Themes, CSS/token refactors, palette contracts, global semantic HTML across themes — **no behavior or API wiring** | WF-036 cosmetic slice — `handoffs/cosmetic-ui-lane.md` |

**Backend lane** must not edit `apps/web/` except when a WF item explicitly requires it.

**UI lane** must not edit `server.py`, session/model/chat wiring, or flip backlog/ledger status.

Pull/rebase before large sweeps; on conflict take backend logic and re-apply cosmetic classes only.

## Agent discipline (mandatory — Alan 2026-07-06)

**Backlog.json may be stale.** Source artifacts win.

Before any patch:

1. **Verify** — grep/read for existing scripts, tests, modules, specs. Run them.
2. **If acceptance already met** — update backlog only (`done` + `evidence` + `completed_at`). **No code changes.**
3. **If partial** — smallest gap only; do not rewrite working paths.
4. **No arbitrary changes** — no drive-by refactors, renames, or style sweeps outside the WF item.
5. **Stay in your lane** — backend agents do backend + wiring; UI agents do cosmetic CSS/themes/global semantic markup only (see parallel lanes above).
6. **Report** — list what you verified, what was already done, what you actually changed.

Quick truth checks (examples):

| Item | Verify with |
|------|-------------|
| WF-006 | `pnpm verify:docs`, `scripts/workframe/verify-docs-claims.mjs` |
| WF-019 | `pnpm test:negative-evidence`, `run-negative-install-evidence.mjs` |
| WF-020 | grep `FirstRunEvidence`, `run-first-run` |
| WF-037 | `python test_route_registry.py`, no `GET_PUBLIC_ROUTES` in server.py |
| WF-039 | `services/workframe-api/domain/`, `test_domain_entities.py` |

## Mission (2026-07-06): push to deferred threshold

Complete **Stages A→D**; **do not** start Stage E items. **Parallel lanes** on `main`: backend (API/ledger) and cosmetic UI (WF-036) — surgical commits only; see `handoffs/cosmetic-ui-lane.md`.

| Stage | Items | Status | Lane |
|-------|-------|--------|------|
| **A** release-truth | WF-006, WF-019, WF-020, WF-004 | **done** | release-truth subagent (commits 2a16df8, 9a06d88) |
| **B** decompose | WF-037, WF-032, WF-035 (API only) | **in flight** (WF-037 done 2026-07-07) | api-decompose subagent |
| **C** secure multi | WF-026→028→027→011→025→017 | queued | broker-secure |
| **D** authority | WF-039→009→NS-P2→016→007, WF-008, WF-010 | queued | domain-design + authority-impl |
| **E** platform | deferred IDs | **STOP** | — |

**Stage gates:** [`program-status.md`](program-status.md) — verified checklist; `ledger-next` picks B→C→D via `backlog.json` `program_stages` (WF-040).

## Current wave: A → B (stabilize + decompose)

| Wave | Items | Parallel? | Status |
|------|-------|-----------|--------|
| A1 | WF-031 security | — | **done** |
| A2 | WF-034 tests, WF-033 yaml writer, WF-038 prune | yes | **done** |
| A3 | WF-006, WF-019, WF-020, WF-004 | yes | **done** |
| B1 | WF-037 route registry | after A2 | **done** (2026-07-07: full registry dispatch; test_route_registry.py) |
| B2 | WF-032 server split | after WF-037 | **partial** (doctor_runtime, api_meta extracted; server ~11k lines) |

## Commit queue (this session)

1. `fix(security): WF-031 close anonymous public GET exposure`
2. `fix(models): billing provider consistency across API and UI`
3. `test(api): WF-034 model surface regression tests`
4. `refactor(api): WF-033 single profile config yaml writer`
5. `chore(monorepo): WF-038 prune stub packages`
6. `docs(ledger): orchestration wave A checkpoint`

## Agent dispatch

```text
Read: docs/ledger/orchestration.md → backlog item handoff_steps → implement → typecheck → commit → update backlog
```
