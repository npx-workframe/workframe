# WF-CLI-003 — Provider-neutral model-assisted dialogue and cancellable verification

**Status:** done (`workframe@0.3.0`, verify path) · **Depends on:** WF-CLI-002 · **Plan:** `docs/ledger/specs/WF-CLI-001/campaign.json`

**Evidence:** `workframe verify --json`, `packages/workframe/lib/inference.js`, `packages/workframe/lib/inference-selection.js`

Explicit inference-path selection (`--select`), separate consent, and cancellable verification are implemented. **Follow-up:** full multi-turn model-assisted dialogue state machine (typed states beyond verify) remains a future slice.

Carries **archived_inference_regressions** from rejected PRs #6–#9 in selection tests: descriptive mentions stay unresolved; mixed clauses require explicit affirmative choice; account vs API-key paths stay separate; inference children use minimal env; Windows `taskkill` on cancel.
