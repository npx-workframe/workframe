# WF-006 — Docs-claim gate

## Problem

Public docs describe multi-user, VPS, adapters, and team modes beyond what release evidence proves today. Version drift was fixed (WF-001); claim drift is the remaining P0.

## Outcome

`verify-docs-claims.mjs` scans `docs/public/` and `README.md` against `operations/release-scope.json`. CI fails on unsupported claims. Planned/experimental/manual wording is allowed via qualifier patterns.

## Scope file

`operations/release-scope.json` lists proven vs not-proven claims and forbidden patterns. Update scope when new evidence types land (e.g. WF-017 public VPS).

## Non-goals

- Scanning `docs/strategy/` or ledger internals
- Blocking documented wizard branches that are qualified as experimental/manual

## Acceptance

See `backlog.json` → `WF-006.acceptance`.

## Verify

```bash
node scripts/workframe/verify-docs-claims.mjs
pnpm verify:docs
```

Wired in `pnpm test:ci` and `.github/workflows/ci.yml`.

## Sources

- `archive/planning/living-audit/25-audit.md` (P0-6)
- `archive/planning/living-audit/current-code-proof-and-forward-plan.md` (Phase 0)
