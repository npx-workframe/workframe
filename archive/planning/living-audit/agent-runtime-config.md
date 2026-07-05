# Agent profile / provider / runtime config model

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
| Product surfaces | `docs/public/using-workframe.md` | `20ee82af97dc8aee9967eea768172d253471eca9` |
| API | `services/workframe-api/server.py` | `52e962760c28ad0eb70240287ed49aa746d3767b` |
| Credential vault | `services/workframe-api/credential_vault.py` | `24250ca7ce034b09e27314bb6548eb925cd08ea3` |
| Turn leases | `services/workframe-api/turn_credentials.py` | `549242d9d30d1928542803a3660512100fbaab7b` |
| LLM proxy | `services/workframe-api/llm_proxy.py` | `41e0ef1f9209d507e84d6d42e03790bc64d3a242` |
| Supervisor | `services/workframe-supervisor/server.py` | `2ffcbfd84da421f59b62bb371f08fc727b560f70` |
| Prior wizard pass | `docs/living-audit/first-run-wizard.md` | `b95a44a1709efdd6b2fdf05701c79b852b09477e` |
| Prior detection pass | `docs/living-audit/runtime-detection-map.md` | `b18f34648656426d455e53f9db9ee391c55b9322` |
| Prior red-team pass | `docs/living-audit/red-team-02-detection-privacy.md` | `77369434aebd5b4931fbcb6a4acedd86147eef68` |

## Planning slice

Agent profile / provider / runtime config model: minimal cell-level schema that lets agents differ by role, runtime adapter, provider, model, funding policy, credential boundary, workspace boundary, and validation state without implementing non-Hermes execution yet.

## Current-state facts

- Public docs still define Workframe as a multi-user web shell around Hermes and advertise UI surfaces including chat, files, browser, activity, direct messages, skills, slash commands, model picker, and Kanban.
- Generated installs currently create `Agents/` for Hermes profiles/state and `Files/` for workspace truth; architecture docs mount these as `/opt/data` and `/workspace`.
- Per-user runtime profiles are documented as `u-{user}-{template}` clones so user keys and chat history stay isolated.
- Security docs define BYOK default, `user_only` providers with no workspace fallback, optional company-pays stack keys, vault encryption, and per-turn lease tokens.
- API code already has a credential vault keyed by binding id, provider, scope, user id, and workspace id.
- Turn-credential leases already bind run id, payer user id, workspace id, provider, credential binding id, and profile slug.
- The LLM proxy already validates lease provider and profile header before resolving a secret and forwarding to OpenRouter, OpenAI, Anthropic, Google, or DeepSeek.
- Supervisor logic is still Hermes-profile-centric: it validates profile slugs, resolves profile directories, configures Hermes profile API ports, starts/stops profile gateways, and guards direct access to runtime profile credential paths.
- Current harness validates API/provider/model surfaces and current installer scaffold, but not role/runtime/provider/funding matrix behavior or non-Hermes adapter contracts.

## Target-state config layers

```text
WorkframeCell
  WorkspacePolicy
  FundingPolicy
  RuntimeAdapterRegistry
  AgentTemplateCatalog
  UserRuntimeProfiles
  RunReceiptLedger

AgentTemplate
  role: architect | coder | docs | research | designer | concierge | custom
  default_capabilities: chat | files | browser | kanban | skills | slash_commands | loops | runs | audit
  default_runtime_preference: hermes_docker_default until another adapter is validated

UserRuntimeProfile
  profile_id: u-{user}-{agent}
  user_id
  agent_template_id
  runtime_binding_id
  provider_binding_policy
  funding_policy_id
  workspace_boundary
  validation_state

RuntimeBinding
  runtime_id
  kind: hermes | codex_cli | claude_cli | cursor | opencode | openclaw | copilot | custom
  scope: workframe_cell | host | docker | remote
  executable: false unless adapter harness is green
  can_start | can_stream | can_cancel | can_capture_logs | can_write_receipt
  credential_boundary: vault_lease | cli_session | oauth_session | none
  workspace_boundary: workframe_files | external_project | unknown

ProviderBindingPolicy
  provider
  model
  credential_scope: user | workspace | delegated_user
  credential_binding_id: vault ref or external session ref
  user_only: true/false
  fallback_allowed: true/false

FundingPolicy
  mode: byok | company_pays | hybrid
  payer_rule: profile_owner | workspace | explicit_delegated_owner
  user_only_no_fallback: always true
```

## Target-state mapping

| User-facing need | Minimal durable config |
|---|---|
| Architect uses GPT-5.5 through Codex OAuth | `AgentTemplate(role=architect)` + inert or validated `RuntimeBinding(kind=codex_cli)` + `ProviderBindingPolicy(provider=openai/codex, model=gpt-5.5, credential_scope=user)` |
| Coder uses Kimi/OpenRouter through Hermes | `UserRuntimeProfile(u-user-coder)` + `RuntimeBinding(kind=hermes)` + vault lease to `ProviderBindingPolicy(provider=openrouter, model=kimi...)` |
| Docs agent uses Claude CLI or Cursor CLI | Same template/profile model, but `executable=false` until the CLI adapter has run/cancel/log/receipt harness coverage |
| BYOK team | `FundingPolicy(mode=byok, payer_rule=profile_owner)` plus per-user credential bindings |
| Company-pays team | `FundingPolicy(mode=company_pays, payer_rule=workspace)` but only for providers where `user_only=false` |
| Hybrid team | User credentials win for user-owned providers; workspace credentials can fund allowed LLM providers only with explicit admin opt-in |
| Delegated run | Run receipt stores assignee/runtime owner, payer rule, provider/model, runtime binding, and workspace/files scope |

## Minimal v0.1.x doctrine

1. Hermes Docker remains the only executable runtime adapter.
2. Non-Hermes runtimes may be represented only as inert candidates or future bindings.
3. Provider/model selection can become adapter-independent before non-Hermes execution exists.
4. Funding policy should be explicit before invites and before scheduled loops.
5. Every run must eventually emit a receipt that records runtime, provider, model, payer, workspace boundary, and validation status.
6. Agent role is not the same as runtime, provider, model, or payer.
7. `user_only` providers never fall back to workspace credentials, even in company-pays mode.

## Config state machine

```text
candidate_detected
  -> hidden_in_primary_wizard
  -> user_expands_candidate
  -> binding_declared
  -> adapter_harness_green
  -> executable_runtime
  -> first_run_verified
  -> selectable_default
```

Hermes Docker may start at `executable_runtime` because it is the current packaged path. All other runtimes must start at `candidate_detected` or `binding_declared` and remain non-executable until validation exists.

## Gaps / risks

- A full role x runtime x provider x model x funding matrix can become untestable before the second adapter exists.
- Current supervisor and session code names profiles and lifecycle around Hermes; adapter-first config needs a seam that does not force every runtime to masquerade as a Hermes profile.
- CLI/OAuth session adapters may not have a clean vault-lease equivalent; they may depend on external sessions with weaker revocation and audit semantics.
- `provider ready` and `runtime ready` are separate states; merging them would create false readiness.
- Workspace boundary differs by adapter: Hermes Docker can mount `Files/`, while host CLIs may see an external project or user home unless strictly launched inside the cell.
- Model picker copy can overpromise if it lists models that are available through a provider but not executable through the selected runtime adapter.
- Company-pays can accidentally become silent fallback unless fallback rules are represented per provider binding and enforced in run receipts.

## Proposed migration / refactor steps

1. Define a planning-only `AgentRuntimeConfig` schema in docs before implementation.
2. Introduce a cell-level adapter registry concept separate from Hermes profile routes.
3. Preserve current Hermes profile execution but wrap it as `RuntimeBinding(kind=hermes, executable=true)`.
4. Move model/provider choice toward `ProviderBindingPolicy`, independent of agent role.
5. Add funding-policy persistence and display before invites: BYOK, company-pays, hybrid.
6. Require run receipt fields before expanding adapters: runtime kind/id, profile id, provider, model, payer, workspace boundary, credential boundary, validation state.
7. Keep non-Hermes candidates hidden from primary setup until one second adapter has start/stream/cancel/log/receipt tests.
8. Add fixture tests for funding fallback and user-only no-fallback before public multi-user expansion.

## Validation gates for this slice

| Gate | Evidence required |
|---|---|
| Role/runtime separation | Architect/coder/docs templates can point at different runtime bindings without duplicating provider rules. |
| Provider/runtime separation | Provider/model can change without changing runtime identity. |
| Funding explicitness | Invites cannot proceed in team/public modes without a recorded BYOK/company/hybrid decision. |
| `user_only` no fallback | User-only provider request fails closed when user credential is absent, even if workspace key exists. |
| Hermes compatibility | Existing Hermes Docker path still satisfies first-chat smoke. |
| Non-Hermes inertness | Non-Hermes binding cannot execute until adapter harness marks it executable. |
| Receipt completeness | Every run can be attributed to runtime, provider, model, payer, workspace boundary, and credential boundary. |

## Open questions for later passes

- Should adapter registry live in `workframe-manifest.json`, API DB, `Agents/workframe`, or all three with one canonical authority?
- What is the exact second adapter to validate first: Codex CLI, Claude CLI, Cursor, OpenCode/OpenClaw, or Copilot?
- Can CLI-session adapters be made compatible with vault leases, or do they need a separate credential-boundary type?
- Should model catalogs be runtime-scoped, provider-scoped, or both?
- What is the minimum run receipt schema that is useful for audit without overbuilding billing infrastructure?

## Next best planning target

Refactor map from current Hermes-centered stack to adapter-first Workframe cell: identify the smallest code seams where `profile_slug == runtime` can become `runtime_binding -> execution adapter` without changing current runtime behavior.
