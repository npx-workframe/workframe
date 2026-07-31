# WF-CLI-005 — Non-destructive Architectonic composition plan

**Status:** done (`workframe@0.3.0`) · **Depends on:** WF-CLI-004 · **Plan:** `docs/ledger/specs/WF-CLI-001/campaign.json`

**Evidence:** `workframe plan --json`, `packages/workframe/lib/plan.js` (`buildArchitectonicPlan`)

Dry-run plan maps draft to Architectonic preset, target root, and additive file paths. Emits suggested `npx architectonic init` command. No package install or filesystem mutation.
