# Workframe Kanban Guide

Role
- Kanban is durable execution and handoff state.

Worker loop
1) read task context
2) execute scoped work
3) heartbeat for long tasks
4) complete with handoff schema
5) block only for real external decisions

Heartbeat cadence
- every 20-30 minutes for long tasks, or at phase boundaries.
- use heartbeat schema from `docs/WORKFRAME_HANDOFF_SCHEMA.md`.

Truth priority
1) files (canonical)
2) Kanban (operational state)
3) chat (coordination surface)
