# WF-016 — Funding modes and run receipts

## Scope (Stage D partial)

- `RunAuthorityGate` selects payer and `FundingSource` (BYOK vs company) before chat stream.
- `run_line_items` records one `llm_turn` receipt per completed chat run.
- `user_only` providers deny workspace fallback (`provider_user_only_no_fallback`).

## Deferred

- USD amounts / token metering on line items
- Hybrid funding policy beyond user-wins-then-workspace
- Non-chat surfaces (kanban, cron, slash)

## Artifacts

- `services/workframe-api/run_authority.py`
- `services/workframe-api/run_ledger.py` (`complete_run`, `insert_line_item`)

## Acceptance

See `backlog.json` → `WF-016.acceptance`.
