# Orchestration — Workframe program execution

**Owner:** pm-workframe (Cursor)  
**Source of truth:** `git` + `docs/ledger/backlog.json`  
**Updated:** 2026-07-05

## Rules

1. **One WF item per commit** when possible — message prefix `fix|test|refactor|chore(scope): WF-xxx …`
2. **Reversible checkpoints** — each commit must pass `pnpm --filter @workframe/workframe-api typecheck`; no mixed unrelated items
3. **Backlog before code** — set `status: in_progress` when starting; `done` + `completed_at` when merged
4. **Handoff** — use `handoff_steps` on the backlog item; agent reads item id only

## Current wave: A → B (stabilize + decompose)

| Wave | Items | Parallel? | Status |
|------|-------|-----------|--------|
| A1 | WF-031 security | — | **done** |
| A2 | WF-034 tests, WF-033 yaml writer, WF-038 prune | yes | **done** (WF-033 partial) |
| A3 | model/provider UI consistency | — | **committed wave 1** |
| B1 | WF-037 route registry | after A2 | **partial** (auth table; handlers pending) |
| B2 | WF-032 server split | after WF-037 | todo |

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
