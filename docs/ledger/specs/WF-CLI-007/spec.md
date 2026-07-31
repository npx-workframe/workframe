# WF-CLI-007 — Explicit apply and rollback authority gates

**Status:** done (`workframe@0.3.0`, simulation only) · **Depends on:** WF-CLI-006 · **Plan:** `docs/ledger/specs/WF-CLI-001/campaign.json`

**Evidence:** `workframe apply --simulate`, `packages/workframe/lib/apply-gate.js`

Approval binds to plan hash (`approve plan <hash>`). Real mutations remain disabled (`real_mutations_enabled: false`). Preflight/rollback simulation only.
