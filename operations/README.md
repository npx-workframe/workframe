# Workframe operations rail

Session-level operator log and pointers to ledgers. **Not** a duplicate of ABKB meta `operations/daily/`.

## Ledgers (two layers)

```text
workframe/.harness/feature_list.json   product verify state (scenarios)
abkb/operations/daily/.../work_items assignment queue (PM → workers)
```

| Need | Read |
|------|------|
| What must pass before release | `.harness/feature_list.json` |
| What task am I doing this run | ABKB `queues.json` → `work_items` |
| Narrative session history | `operations/log.md` (here) |
| Ontology + pitfalls | ABKB `projects/workframe/` + repo `START_HERE.md` |

## Log

Append-only: `operations/log.md` — `ISO timestamp | Role | outcome`

## Roles

Registry: `abkb/operations/roles/registry.json`

- **pm-workframe** — plans, enqueues `work_items`, no product code in PM pass
- **coder / tests / docs / code-reviewer** — one `work_items` entry per run

Prompts: `abkb/operations/roles/pm-workframe/prompt.md` and `workers/*/prompt.md`.
