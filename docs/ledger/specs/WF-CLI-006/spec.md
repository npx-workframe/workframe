# WF-CLI-006 — Dry-run Workframe deployment plan

**Status:** done (`workframe@0.3.0`) · **Depends on:** WF-CLI-005 · **Plan:** `docs/ledger/specs/WF-CLI-001/campaign.json`

**Evidence:** `workframe plan --json`, `packages/workframe/lib/plan.js` (`buildDeploymentPlan`)

Non-destructive deployment recommendation from host capabilities and execution-surface answer. Does not invoke `create-workframe`, Docker, or network changes. `architectonic_only` vs `create_workframe_docker` branching.
