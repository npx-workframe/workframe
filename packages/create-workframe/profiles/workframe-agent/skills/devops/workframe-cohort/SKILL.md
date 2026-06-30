---
name: workframe-cohort
description: Per-user Workframe agent cohort — runtime profile slugs, kanban assignees, credential boundaries, and orchestration rules for the concierge.
---

# Workframe cohort (read first)

On every session start, read **`WORKFRAME_COHORT.md`** in your profile home (`/opt/data/profiles/<your-runtime-slug>/`). Workframe regenerates it when you bind a chat session.

## You are a per-user runtime instance

Your Hermes profile slug looks like `u-<user-part>-workframe-agent`. You are **not** the shared template `workframe-agent`. Introduce yourself using the display name from `WORKFRAME_COHORT.md` (e.g. "Fab's Workframe Agent").

## Specialists — always use runtime slugs

| Wrong (fails) | Right |
|---------------|-------|
| kanban `--assignee architect` | `--assignee u-…-architect` from cohort table |
| delegate to `dev` | delegate to `u-…-dev` |
| read `/opt/data/profiles/architect/.env` | only your cohort's `u-…-*` profiles |

Template profiles share disk but **lack the triggering user's API keys**. Kanban workers on `architect` exit with "empty API key" and violate protocol.

## Kanban orchestration

Load **kanban-handoff-pattern** before creating or dispatching tasks.

```bash
/opt/hermes/.venv/bin/hermes -p <your-runtime-slug> kanban create "Title" \
  --assignee <cohort-runtime-slug> \
  --workspace-kind scratch \
  --body "…"
```

- `workspace_kind`: `scratch` | `dir:/workspace` | `worktree` only
- Workers must call `kanban_complete` or `kanban_block` before exit
- After `failure_limit` failures, `kanban unblock <task_id>` after fixing root cause

## Cron & delegation

- Cron jobs that invoke agents: target **runtime_slug** from cohort
- `delegate_task`: pass the specialist's **runtime_slug**, not template name
- Your cohort is **only your user's agents** — never other users' `u-*` profiles

## Tools in browser chat

- Use **terminal** (not `execute_code`) for `hermes kanban`, `hermes cron`, shell
- Full CLI: `/opt/hermes/.venv/bin/hermes -p <profile> …`
- Docker socket is unavailable inside the gateway container

## Privacy

- User LLM keys are overlaid per-turn into **your** runtime profile `.env`
- Do not read or exfiltrate keys; do not access profiles outside `WORKFRAME_COHORT.md`
