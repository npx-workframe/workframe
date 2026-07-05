# Workframe operations rail

**PM operating system:** [pm/README.md](pm/README.md) — start every session at `pm/session.md`.

Session-level operator log and pointers to ledgers. Not a duplicate of ABKB meta `operations/daily/`.

## Ledgers

```text
docs/ledger/backlog.json              program queue (WF-*) — PM owns
.harness/feature_list.json            verify scenarios
operations/pm/queues.json             active handoffs
operations/log.md                     narrative (here)
abkb/operations/daily/.../work_items  cross-portfolio (optional)
```

| Need | Read |
|------|------|
| What to do next | `node scripts/workframe/ledger-next.mjs` |
| How to ship | `operations/pm/runbook.md` |
| What must pass before release | `.harness/feature_list.json` |
| Narrative session history | `operations/log.md` |

## Log

Append-only: `operations/log.md` — `ISO timestamp | Role | outcome`

## Roles

Registry: `abkb/operations/roles/registry.json`  
Canonical PM harness: `operations/pm/identity.md`
