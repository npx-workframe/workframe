---
name: kanban-handoff-pattern
description: Kanban task handoff from Workframe concierge to user-scoped specialist runtime profiles — workspace_kind, assignee slugs, worker protocol, failure modes.
---

# Kanban handoff pattern

**Prerequisite:** Read `WORKFRAME_COHORT.md` and use **runtime_slug** as `--assignee`, never bare template names (`architect`, `dev`).

## Kanban vs delegate_task

| Use kanban when | Use delegate_task when |
|-----------------|------------------------|
| Durable work, audit trail, human review | Quick parallel subtasks in one turn |
| Specialist may take minutes | Parent turn bounds the work |

## Create a task (CLI)

```bash
/opt/hermes/.venv/bin/hermes -p <your-runtime-slug> kanban create "Title" \
  --assignee <specialist-runtime-slug-from-cohort> \
  --workspace-kind scratch \
  --body "Goal…\n\nOutput: /workspace/docs/…"
```

### workspace_kind (only these)

- `scratch` — default, isolated temp dir (safest)
- `dir:/absolute/path` — e.g. `dir:/workspace`
- `worktree` — git worktree

Using `project`, `repo`, or anything else → `spawn_failed: unknown workspace_kind`.

## Worker protocol (specialists)

1. `kanban_show` — orient
2. Do the work; write outputs to paths in task body
3. `kanban_comment` — handoff notes for reviewer
4. **`kanban_complete(summary=…)`** or **`kanban_block(reason=…)`** before exit

Clean exit without complete/block → protocol violation → auto-block after `failure_limit` (default 2).

## Failure modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| empty API key | assignee is template slug, not runtime | cohort runtime_slug |
| unknown workspace_kind | invalid kind in DB/CLI | recreate with `scratch` |
| protocol violation | worker died without complete/block | fix credentials + skills |
| task blocked | failure_limit tripped | fix root cause, `kanban unblock` |

## Verify

```bash
/opt/hermes/.venv/bin/hermes -p <profile> kanban list
/opt/hermes/.venv/bin/hermes -p <profile> kanban show <task_id>
/opt/hermes/.venv/bin/hermes -p <profile> kanban log <task_id>
```
