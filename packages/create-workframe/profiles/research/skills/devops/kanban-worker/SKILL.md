---
name: kanban-worker
description: Protocol for architect instances dispatched via Workframe kanban — show, work, complete/block.
---

# Kanban worker (you were dispatched)

You are running as a **user-scoped runtime profile** (`u-…-architect`), not the shared template `architect`. Your credentials come from the owning user's overlay.

## Required lifecycle

1. `kanban_show` — read task id, body, output paths
2. Execute the work (terminal, write_file, read_file)
3. `kanban_comment` — files changed, decisions, test notes
4. **`kanban_complete(summary=…, metadata=…)`** when done  
   OR **`kanban_block(reason=…)`** if stuck

Never exit without step 4 — the dispatcher treats it as a protocol violation.

## Workspace

- Task `workspace_kind` is usually `scratch` or `dir:/workspace`
- Write deliverables to paths specified in the task body (under `/workspace` when shared)

## If you lack API access

If provider resolver returns empty API key, call `kanban_block` explaining misconfiguration — do not exit silently.
