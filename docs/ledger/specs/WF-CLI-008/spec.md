# WF-CLI-008 — Packed cross-platform Socratic CLI evidence

**Status:** done (`workframe@0.3.0`) · **Depends on:** WF-CLI-007 · **Plan:** `docs/ledger/specs/WF-CLI-001/campaign.json`

**Evidence:** `packages/workframe/test/cli.test.mjs`, `npm pack` clean-install smoke on Windows (Node 24)

Packed tarball installs; npm bin runs `begin --json`, `capabilities`, `draft`. Publication to npm remains a separate release decision.
