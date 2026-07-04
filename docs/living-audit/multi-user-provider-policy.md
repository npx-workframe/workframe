# Multi-user / BYOK / company-pays journey

Temporary living-audit planning material. Not public release doctrine. Planning only; no product source-code changes are implied by this file.

## Inspected ref / SHAs

Repository resolved directly: `npx-workframe/workframe`, default branch `main`.

| Area | Path | Blob SHA |
|---|---|---|
| Entry | `README.md` | `b97cd64e4f899dc758bb73a0e04ec9a89a344317` |
| Agent rules | `AGENTS.md` | `f648f29fdb9569c3bb7a5c6c8e178173582cde03` |
| Repo map | `START_HERE.md` | `cf65246dc937256099d8297e79487635c3b724d2` |
| Harness docs | `.harness/README.md` | `e21ce2d468b8f8baaa4660edf7054bd04d4f7ec0` |
| Harness scenarios | `.harness/feature_list.json` | `ed32c988e668d813e99d8f332ebd2d22b3fbb95e` |
| Harness runner | `.harness/verify.mjs` | `e8785ebc99091abfa295e9062613c4db208c840f` |
| Monorepo package | `package.json` | `7b8232a887d2c3558078c18cbbc6cac20051f363` |
| Installer package | `packages/create-workframe/package.json` | `72fc7bf7625c8e786baf0f9d44c389e5f4ad6547` |
| Docs index | `docs/README.md` | `e8a2a847ef29f784655f348fb1a53e535ff4915e` |
| Install docs | `docs/public/install.md` | `0ece45f99eb63781e090faefa670a61d3f33d265` |
| Architecture docs | `docs/public/architecture.md` | `df9acf46cad326df2a6e211dfd48608794ee42b4` |
| Security docs | `docs/public/security.md` | `3ab7a2408a92be7e8b6115bd798684b342cd5424` |
| Session docs | `docs/public/session-architecture.md` | `65481ee7cac21e4575b3284be7a6d5d2bdcd1c62` |
| Using docs | `docs/public/using-workframe.md` | `20ee82af97dc8aee9967eea768172d253471eca9` |
| Operations docs | `docs/public/operations.md` | `06dae7747e242f59a6c82b1ea5d01a101d8a0e4b` |
| Public deploy docs | `infra/compose/workframe/PUBLIC_DEPLOY.md` | `2a6ec3188a5e75023b2a11aeaed778e06c12d6da` |
| Prior agent/runtime config | `docs/living-audit/agent-runtime-config.md` | `9c6aa041be1c83d84165b54803db38ee32e48858` |
| Prior surface baseline | `docs/living-audit/workframe-surface-baseline.md` | `6d5e877363c6cdbd69413d1f5b5b03c4c8c4b5d7` |
| Operator log | `operations/log.md` | `23f45d3c1690dc806fb1f123f9a928f025cf8484` |

## Planning slice

Multi-user / BYOK / company-pays journey: define the smallest understandable funding and credential policy for team use while v0.1.x still executes only managed Hermes Docker and does not claim billing-grade accounting.

## Current-state facts

- README describes Workframe as a multi-user web shell around Hermes, with UI, API, installer, and Docker Compose packaging.
- The install wizard includes deployment mode, SMTP/admin for team/public, optional integrations, model billing, business profile, user profile, model keys, native agent, invites, and launch.
- Deployment modes are `single_user_local`, `trusted_team`, and `public_multi_user`; public mode requires HTTPS, SMTP, vault/secrets, proxy token, and supervisor token.
- Security docs define BYOK as default, `user_only` providers as no-fallback, company-pays as admin opt-in, vault encryption, and per-turn lease tokens.
- Architecture docs identify credentials as BYOK default, `user_only` no workspace fallback, company-pays stack keys on the native profile, and vault-backed per-turn leases.
- Session docs bind browser chat to per-user runtime profiles named `u-{user}-{template}` so keys and chat history stay isolated.
- Operations docs say each user connects LLM keys and agent chat / @mentions require the acting user to have an LLM provider connected.
- Public deploy docs say Kanban delegation charges the assignee owner, not the initiator.
- Current harness has API/provider/model checks, but no explicit multi-user funding journey gate, no invite funding gate, and no run-receipt gate.
- Prior planning narrowed v0.1.x execution to managed Hermes Docker; non-Hermes runtimes remain inert candidates until adapter harnesses exist.

## First-principles policy

A team run needs five separate decisions before execution:

```text
actor
  -> target agent/profile
  -> runtime binding
  -> provider/model binding
  -> payer rule
  -> run receipt
```

Do not collapse these into a model picker. The model picker selects capability. Funding policy determines who pays. Runtime binding determines where execution happens. A run receipt proves what happened.

## Minimal user journey

### Single-user local

```text
wizard chooses single_user_local
  -> user may skip SMTP
  -> funding mode implicitly BYOK/local
  -> user connects provider key or sees no-key state
  -> managed Hermes profile runs only when user key exists
```

Do not show company-pays as a meaningful choice here. It creates false enterprise semantics for a solo cell.

### Trusted team Docker/LAN

```text
owner chooses trusted_team
  -> owner chooses funding mode before invites
  -> BYOK: each member must connect own LLM key before own agent runs
  -> company-pays: owner/admin connects workspace LLM key for allowed providers
  -> hybrid: user key wins; workspace key is explicit fallback only for allowed non-user-only LLM providers
  -> invitees see the active funding policy during onboarding
```

The team journey must make cost authority visible before people start delegating work.

### Public VPS / self-hosted

```text
owner chooses public_multi_user
  -> HTTPS/SMTP/secrets/allowlist gates pass first
  -> owner chooses invite policy and funding policy
  -> default remains BYOK unless owner explicitly enables company-pays or hybrid
  -> workspace keys never satisfy user_only providers
  -> every run writes at least a non-billing receipt
```

Public mode must fail closed when policy is missing. A public install with ambiguous funding is not launch-ready.

### Delegated work

```text
Bob asks Alice-owned agent to run
  -> actor = Bob
  -> assignee/profile owner = Alice
  -> payer = profile owner unless explicit workspace/company policy applies
  -> receipt records actor, assignee, payer, runtime, provider, model, credential scope
```

Delegation grants assignment authority, not key lending.

## Target-state mapping

| Funding mode | Credential source | Default payer | Workspace fallback | User-only providers |
|---|---|---|---|---|
| BYOK | Per-user vault binding | Profile owner / acting user depending on profile ownership | No | Must fail closed |
| Company-pays | Workspace/admin vault binding for allowed LLM providers | Workspace | Yes, but only when policy allows | Must fail closed |
| Hybrid | User binding first, workspace binding second | User if user key used; workspace if workspace key used | Explicit only | Must fail closed |
| Delegated user-owned profile | Assignee/profile-owner binding | Profile owner | No unless explicit team policy | Must fail closed |

## Required state objects

```text
WorkspaceFundingPolicy
  mode: byok | company_pays | hybrid
  set_by_admin_user_id
  applies_to_provider_kinds: llm_only for v0.1.x
  user_key_precedence: true
  workspace_fallback_allowed: false by default
  user_only_no_fallback: true always
  effective_from

ProviderBinding
  owner_scope: user | workspace
  owner_id
  provider
  model_allowlist optional
  user_only: boolean
  redacted_status

RunFundingDecision
  actor_user_id
  profile_owner_user_id
  workspace_id
  provider
  model
  credential_scope: user | workspace
  credential_binding_id redacted/ref
  payer_scope: user | workspace
  payer_id
  fallback_used: boolean
  decision_reason

RunReceiptMinimum
  run_id
  timestamp
  actor_user_id
  agent_profile_id
  runtime_kind: hermes for v0.1.x
  provider
  model
  payer_scope
  payer_id
  credential_scope
  workspace_boundary
  status: started | completed | failed | cancelled
```

## Gaps / risks

- Current docs mention BYOK, company-pays, hybrid-adjacent behavior, user-only no-fallback, and assignee-owner payment, but the user journey is spread across install, architecture, security, operations, public deploy, and prior planning docs.
- `acting user has key` and `profile owner pays` can conflict unless run funding decision is explicit for DMs, spaces, and delegated Kanban work.
- Company-pays can become silent fallback if model picker simply finds any available workspace key.
- Public mode can appear secure while still lacking understandable cost authority for invited members.
- `user_only` is currently a policy phrase; release evidence needs a direct no-fallback test before company-pays is marketed.
- Billing-grade receipts are too much for v0.1.x, but no receipt at all makes audit/activity and cost debugging weak.
- Workspace keys on a native profile are Hermes-shaped; adapter-first Workframe later needs workspace credentials that are not tied to one runtime's profile layout.

## Proposed migration / refactor steps

1. Add a planning-visible `WorkspaceFundingPolicy` concept before implementing billing or second adapters.
2. Require funding mode selection before invites in `trusted_team` and `public_multi_user` wizard paths.
3. Keep `single_user_local` effectively BYOK/local and avoid company-pays copy there.
4. Treat workspace credentials as allowed only for LLM providers in v0.1.x; OAuth/dev-tool providers remain `user_only`.
5. Add a no-fallback invariant: user-only provider request without a user binding fails even if a workspace binding exists.
6. Add a minimal run receipt for Hermes runs before adding non-Hermes adapters or scheduled loops.
7. Surface the effective payer before run start for agent DMs, space @mentions, and delegated Kanban work.
8. Write activity/audit events from the funding decision, not from inferred provider availability.
9. Defer billing-grade accounting, invoices, quotas, seat pricing, and spend dashboards until the non-billing receipt is reliable.

## Validation gates for this slice

| Gate | Evidence required |
|---|---|
| Funding selected before invites | Team/public wizard cannot invite until BYOK/company/hybrid is recorded. |
| BYOK no-key state | Invited member with no key sees clear no-key state and cannot run agent chat. |
| Company-pays explicitness | Workspace key is used only after admin opt-in and visible policy acknowledgement. |
| Hybrid precedence | User key wins over workspace key unless user has no key and fallback is explicitly allowed. |
| User-only no-fallback | GitHub/Vercel/Cursor/Copilot-style provider cannot use workspace credentials. |
| Delegation payer clarity | Delegated run records actor, profile owner, payer, provider, model, and reason. |
| Public fail-closed | Public mode refuses ambiguous funding/provider state before launch claim. |
| Receipt minimum | A Hermes run emits the minimum receipt fields without promising billing accuracy. |

## Open questions for later passes

- Should BYOK payer be always `profile_owner`, or should human-owned direct actions use `actor` when actor and profile owner differ?
- Where is the canonical `WorkspaceFundingPolicy`: API DB, `workframe-manifest.json`, stack config, or a versioned combination?
- Should workspace LLM keys live in API vault only, or also materialize as short-lived profile leases like user keys?
- What is the first UI surface that should display effective payer: model picker, chat composer, run receipt, or activity feed?
- Should public mode require quotas before company-pays can be enabled, or only before broad invites?

## Next best planning target

Final convergence synthesis: compress the installer, runtime detection, deployment order, adoption policy, surface baseline, funding policy, release gates, validation plan, and red-team findings into a single v0.1.x → v0.2 roadmap with explicit deferrals.
