# Now — shipping wedge (v0.1.x)

**Last updated:** 2026-07-05  
**Package:** `0.1.11` (see [VERSION.md](../VERSION.md))

## One line

Hermes-native **multi-user Workframe cell** on Docker/VPS: invite teammates, BYOK/company-pays, vault + per-turn leases, in-app updates — not the full north-star marketplace/cell manager yet.

## Shipped (this wedge)

| Area | Status | Evidence |
|------|--------|----------|
| Docker stack (UI, API, gateway, supervisor) | shipped | `infra/compose/workframe/` |
| Multi-user auth, invites, RBAC | shipped | `services/workframe-api/` |
| Credential vault + `wf_rt_*` leases | shipped | `credential_vault.py`, `turn_credentials.py` |
| Internal LLM proxy (lease → provider) | shipped | `llm_proxy.py` |
| Model/settings unification | shipped | v0.1.8+ |
| In-app Workframe update (SECURE_MODE) | shipped | v0.1.9–0.1.11 |
| Public deploy verify script | shipped | `scripts/workframe/verify-public-deploy.sh` |
| Agent egress doctrine (docs) | shipped | [security.md](../public/security.md) |
| Harness verify (cloud/API/build/scaffold) | partial | `.harness/verify.mjs` — install-gate still local |

## Active (next proof layers)

From [final convergence synthesis](../../archive/planning/living-audit/final-convergence-synthesis.md):

1. **PackageTruthGate** — one credible wipe → `create-workframe` → wizard → chat path with version parity.
2. **Forced egress broker** — network-unavoidable credential traffic (`WORKFRAME_FORCE_AGENT_EGRESS_BROKER` is **planned**, verify fails if set).
3. **Runtime adapter seam** — `runtime_kind` column + resolver; Hermes remains default executable runtime.
4. **Run ledger** — authority, cost, artifacts, audit per run (north-star primitive; minimal hooks today).

## Explicitly deferred (north star)

- Cell manager / hosted provisioning
- Full tool broker beyond LLM + action proxy
- Billing line items / marketplace
- Non-Hermes engine adapters (Codex CLI, Pi, etc.) as first-class runtimes

## Public docs map

| Audience | Doc |
|----------|-----|
| Evaluator | [security.md](../public/security.md) → [audit.md](../public/audit.md) |
| Operator | [install.md](../public/install.md) → [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md) |
| Contributor | [develop.md](../public/develop.md) → [AGENTS.md](../../AGENTS.md) |
