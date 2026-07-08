# Now — shipping wedge (v0.1.x)

**Last updated:** 2026-07-08  
**Package:** `0.1.12` (see [VERSION.md](../VERSION.md))  
**Active plan:** [gate-run-2026-07-08.md](handoffs/gate-run-2026-07-08.md) — close Stages A→D, stop at E

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
| Harness verify (cloud/API/build/scaffold) | shipped | `.harness/verify.mjs` |
| Dogfood sign-off (MyBusiness Docker) | **done** | Alan 2026-07-05 — wizard + chat |

## Active (next proof layers)

From [final convergence synthesis](../../archive/planning/living-audit/final-convergence-synthesis.md):

1. **PackageTruthGate** — **done** (Alan sign-off MyBusiness Docker; WF-020 automates FirstRunEvidence JSON).
2. **Forced egress broker** — **done** (WF-025: compose + iptables enforcement; WF-027 broker audit events).
3. **Run ledger** — **landed** (WF-NS-P2: runs/run_events/run_line_items; chat, mention, kanban, cron, slash, webhook surfaces record; activity panel reads run_events). Receipts per run (WF-016 slice) in flight.
4. **Runtime adapter seam** — `runtime_kind` column + resolver; **deferred to E gate** (Hermes remains the only executable runtime this wedge).

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
