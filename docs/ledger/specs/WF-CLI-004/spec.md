# WF-CLI-004 — Constitutional entity and goal draft

**Status:** done (`workframe@0.3.0`) · **Depends on:** WF-CLI-003 · **Plan:** `docs/ledger/specs/WF-CLI-001/campaign.json`

**Evidence:** `workframe draft --json`, `packages/workframe/lib/mirror.js` (`buildConstitutionalDraft`)

In-memory entity draft: authority root, purpose, identity, goals, constraints, success criteria, unresolved questions, and provenance per field. Stable JSON feeds planning slices; no file writes in this command.
