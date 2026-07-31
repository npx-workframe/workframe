# WF-CLI-002 — Truthful runtime and provider capability graph

**Status:** done (`workframe@0.3.0`) · **Depends on:** WF-CLI-001 · **Plan:** `docs/ledger/specs/WF-CLI-001/campaign.json`

**Evidence:** `workframe capabilities --json`, `packages/workframe/lib/capability-graph.js`

Extend the standalone CLI with a deterministic capability graph that lists installed runtimes, account-backed access, configured direct-provider access, credential source, payer, invocation mode, cancellation support, and non-destructive constraints as **distinct candidates**—without inference, provider calls, installation, adoption, or filesystem mutation. Installed must not imply authenticated; authenticated must not imply verified; verification must not imply installation authority. Account-backed and API-key-backed paths stay separate with exact credential class and payer disclosure. No candidate is selected automatically.
