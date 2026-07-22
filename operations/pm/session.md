# PM session

1. Confirm repository and branch with `git status -sb`.
2. Read `AGENTS.md` and `docs/ledger/ledger.json` when durable coordination is required.
3. Select one eligible item with `node scripts/workframe/ledger-next.mjs`, or use the explicitly assigned item.
4. Verify source truth before changing code; if acceptance is already met, record evidence without code churn.
5. Execute the smallest coherent patch through `runbook.md`, verify, record the transition, and stop.

Dogfood reset remains `scripts/workframe/reset-dogfood-docker.ps1 -Confirm`;
the local UI remains `http://127.0.0.1:18644`.
