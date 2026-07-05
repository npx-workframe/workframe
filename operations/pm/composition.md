# PM composition — ABKB, Architectonic, spec-kit

How layers stack when the Workframe PM (or a worker) runs.

## Formula (ABKB)

```text
role     = identity + skills + prompt + ledger_scope + automation_binding
project  = knowledge + skills + prompt + ledger + code + artifacts + docs
```

## Workframe PM stack

```text
operations/pm/identity.md          ← who (this repo)
abkb/operations/roles/pm-workframe/prompt.md   ← automation variant
projects/workframe/agent-rail.md   ← pitfalls (ABKB)
START_HERE.md                      ← repo map
docs/ledger/backlog.json           ← program queue
operations/pm/runbook.md           ← how to ship
```

## Spec-kit mapping

| Spec-kit phase | Workframe artifact |
|----------------|-------------------|
| constitution | `AGENTS.md` + `docs/ledger/north-star.md` + `docs/public/security.md` |
| specify | `docs/ledger/specs/<WF-ID>/spec.md` |
| plan | `docs/ledger/specs/<WF-ID>/plan.md` |
| tasks | `backlog.json` → `acceptance[]` or `tasks.md` |
| implement | coder role + runbook |
| (gap) review | `code-reviewer` + `status: review` |

See [docs/ledger/spec-kit.md](../../docs/ledger/spec-kit.md). Future: `specify init --integration cursor`.

## Architectonic mapping

| Package | Use for Workframe |
|---------|-------------------|
| `architectonic-living-knowledge` | Loop pattern: Observe→Persist, daily ledger, queues |
| `architectonic-meta` | Self-audit / upkeep discipline |
| `architectonic-project` | Cell vocabulary (north star) |
| Org repos (autocorp, mktintel, TKG) | **ChatGPT** schedulers — PM reads supervisor digest, does not mutate |

Workframe PM scheduler: **Cursor** (`abkb/operations/registry/scheduler-ownership.md`).

## Selection order (every run)

```text
North Star (docs/strategy) → backlog wave → backlog item → role → patch → ledger update → stop
```

One role per automation run. PM pass does not also code-review in same unattended turn unless Alan asks.

## Enqueue worker from backlog

```json
{
  "id": "wi-wf-20260705-1",
  "backlog_id": "WF-001",
  "assignee_role": "tests",
  "title": "Version agreement verifier script",
  "acceptance": "From backlog.json WF-001",
  "status": "queued"
}
```

Write to `operations/pm/queues.json` and optionally ABKB `operations/daily/YYYY-MM-DD/queues.json`.
