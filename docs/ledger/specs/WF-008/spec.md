# WF-008 — Mutation-free doctor

## Problem

Install docs expose `workframe doctor` as optional preflight. Users may treat doctor output as permission to mutate. Doctor must remain advisory and never read secrets or write host state.

## Outcome

`workframe doctor --json` emits a structured, redacted detection report for Docker, Node, cell manifest, and runtime candidates. No credential material. No filesystem mutation.

## JSON schema (v0.1)

```json
{
  "schema_version": "0.1",
  "advisory_only": true,
  "decision": "healthy | needs_user_action | unhealthy",
  "project": {
    "name": "string",
    "package_version": "string | null"
  },
  "checks": {
    "docker": { "status": "ok|fail", "note": "string" },
    "node": { "status": "ok|fail|skip", "version": "string | null" },
    "manifest": { "status": "ok|fail", "stack": "string | null" },
    "layout": { "status": "ok|fail", "workspace": "ok|missing", "runtime": "ok|missing" },
    "cell": { "deployment_mode": "string | null", "install_id_redacted": "string | null" },
    "runtime_candidates": [
      { "kind": "hermes_managed", "status": "running|stopped|unknown", "service": "gateway" }
    ]
  },
  "issues": ["string"]
}
```

## Rules

- `advisory_only` is always `true` — not a gate decision (WF-007 consumes doctor for open checks).
- Paths redacted to project-relative names only.
- Never read `.env` values, profile `.env`, vault, or API keys.
- `--json` mode performs no `docker compose up`, repair, or file writes.

## Implementation

`packages/create-workframe/bin/workframe.js` — `cmdDoctor(root, { json: true })`.

## Acceptance

See `backlog.json` → `WF-008.acceptance`.
