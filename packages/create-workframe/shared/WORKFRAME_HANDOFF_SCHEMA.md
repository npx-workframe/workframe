# Workframe Handoff Schema

Every completed specialist task should include:

Required
- summary: what was done
- changed_files: absolute or repo-relative paths
- next_action: concrete next step
- owner: next responsible profile/person

Recommended
- decisions: key choices made
- assumptions: unresolved assumptions
- blockers: explicit question if blocked
- evidence: links/refs/tests for verification

Heartbeat schema (for long-running tasks)
- state: phase name
- progress: short status
- eta: rough estimate
- risk: only if material risk changed

Storage
- heartbeat/handoff in Kanban comments
- durable result in project files
