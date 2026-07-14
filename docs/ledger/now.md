# Now — shipping wedge (v0.1.x)

**Last updated:** 2026-07-12
**Package:** `0.1.19` (see [VERSION.md](../VERSION.md))
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

### 2026-07-12 stabilization finding

- Package-install and negative-install evidence now match `0.1.18`; the release verifier fails closed on stale evidence.
- The Docker UI/API/gateway/supervisor stack is healthy after a bounded service recycle.
- Browser chat exposed the remaining blocker: the generated Codex runtime profile selects `gpt-5.4-medium`, which Codex through a ChatGPT account rejects with HTTP 400. The UI model badge can show `gpt-5.4-mini` while dispatch still reads the stale generated profile.
- Canonical source now makes `gpt-5.4-mini` the Codex MVP/default and removes the unsupported medium model from the Codex picker. Focused model-surface tests pass.
- That required proof was completed in the release-candidate result below.

### 2026-07-12 release candidate result

- `create-workframe@0.1.19` is the current candidate; version agreement passes.
- Canonical API, installer mirror, packed artifact, and non-destructive MyBusiness dogfood preview contain the Codex profile migration fix.
- Authenticated browser proof passed: `WORKFRAME_OK — ABX` from `gpt-5.4-mini`; refresh also showed the composer on `gpt-5.4-mini`.
- Package-install, negative-install, and FirstRunEvidence all allow at `0.1.19`; `verify-release-gates.mjs` allows all tracked gates.
- Public-repository verification passes. npm publication has **not** occurred because `npm whoami` returns `401 Unauthorized`.
- **Next action:** authenticate npm as the package owner, rerun `npm whoami`, publish 0.1.19, then update and verify the three VPS cells through the supported update/install workflow.

### 2026-07-12 VPS target preflight

- `abx.alanborger.com`, `dev.click.blue`, and `demo.workfra.me` currently have no public DNS records, so HTTPS deployment cannot yet complete.
- The existing Hetzner-backed `dev.alanborger.com` record resolves to `95.216.136.200`; the three requested A records should target that address unless the operator intends a different host.
- The configured Hetzner host is reachable. Its existing slot-2 `MyBusiness` cell is `create-workframe@0.1.7`, healthy for ten days, and reports secure `public_multi_user` posture; Caddy exposes it only at `dev.alanborger.com`.
- The host has approximately 6.4 GB available memory and 134 GB free disk. Workframe slots 3, 4, and 5 are unbound and can host the three requested cells after package publication, DNS, SMTP/invite configuration, and per-cell backup/restore planning are resolved.

From [final convergence synthesis](../../archive/planning/living-audit/final-convergence-synthesis.md):

1. **PackageTruthGate** — **done** (Alan sign-off MyBusiness Docker; WF-020 automates FirstRunEvidence JSON).
2. **Forced egress broker** — **done** (WF-025: compose + iptables enforcement; WF-027 broker audit events).
3. **Run ledger** — **landed** (WF-NS-P2: runs/run_events/run_line_items; chat, mention, kanban, cron, slash, webhook surfaces record; activity panel reads run_events). WF-016 receipt wiring is done; `amount_usd` remains null until pricing/billing work is admitted past the E stop line.
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
