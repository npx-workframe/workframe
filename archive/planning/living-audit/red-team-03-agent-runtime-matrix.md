# Red team 03 — agent/runtime/provider matrix risk

Temporary living-audit planning material. Not public release doctrine. Planning only; no product source-code changes are implied by this file.

## Inspected ref / SHAs

Repository resolved directly: `npx-workframe/workframe`, default branch `main`.

| Area | Path | Blob SHA |
|---|---|---|
| Entry | `README.md` | `b97cd64e4f899dc758bb73a0e04ec9a89a344317` |
| Agent rules | `AGENTS.md` | `f648f29fdb9569c3bb7a5c6c8e178173582cde03` |
| Repo map | `START_HERE.md` | `cf65246dc937256099d8297e79487635c3b724d2` |
| Living audit base | `docs/living-audit/README.md` | `bcae35adef77b46c6774c9efbd075c2e0229b0ca` |
| First-run wizard pass | `docs/living-audit/first-run-wizard.md` | `b95a44a1709efdd6b2fdf05701c79b852b09477e` |
| Runtime detection pass | `docs/living-audit/runtime-detection-map.md` | `b18f34648656426d455e53f9db9ee391c55b9322` |
| Agent runtime config pass | `docs/living-audit/agent-runtime-config.md` | `9c6aa041be1c83d84165b54803db38ee32e48858` |
| Prior red team 01 | `docs/living-audit/red-team-01-adoption-risk.md` | `cf5ab6a80f2341fdeafb6aac6d1ada158493e057` |
| Prior red team 02 | `docs/living-audit/red-team-02-detection-privacy.md` | `77369434aebd5b4931fbcb6a4acedd86147eef68` |
| Operator log | `operations/log.md` | `a3a7eead0b660180f5aa58033002c48f365f8bf6` |

## Planning slice challenged

Adversarial review of `agent-runtime-config.md`, focused on whether agent role, runtime adapter, provider/model, funding policy, credential boundary, workspace boundary, and delegation billing can be represented without creating an untestable product matrix before a second executable adapter exists.

## Current-state facts

- Repository instructions require source artifacts over memory, simplicity before complexity, and canonical source edits rather than installer-copy-only changes.
- The current repository still presents Workframe as a multi-user web shell around Hermes and the public install command still points at `create-workframe@0.1.6`.
- Existing planning now correctly separates `DetectedRuntimeCandidate` from `ValidatedRuntimeAdapter` and recommends Hermes Docker as the only executable default until another adapter is validated.
- The latest config model introduces many orthogonal axes: agent role, runtime kind, runtime scope, provider, model, credential scope, funding mode, payer rule, workspace boundary, validation state, and run receipt fields.
- Existing docs already define per-user Hermes profiles as `u-{user}-{agent}` and security doctrine around BYOK, `user_only` no-fallback, vault, and leases.
- The latest planning proposes hiding non-Hermes candidates until a second adapter has start/stream/cancel/log/receipt tests, but the schema itself still invites early generalization.

## Red-team contradictions / weak assumptions

### 1. A correct ontology can still be the wrong next product move

The config model is conceptually sound: role is not runtime, runtime is not provider, provider is not payer. The risk is sequencing. If implementation begins from the full matrix, the product will inherit complexity before there is evidence that users need more than one executable adapter.

Simpler rule: implement only the fields required to make the current Hermes path safer and auditable. Represent future adapters as documentation and inert records, not first-class UI choices or runtime paths.

### 2. `profile_id = u-{user}-{agent}` may smuggle Hermes assumptions into adapter-first design

The model keeps the existing profile slug shape. That is compatibility-friendly, but risky if future adapters are forced to impersonate Hermes profiles. Claude CLI, Codex CLI, Cursor, Copilot, or OpenCode may not map cleanly to a long-lived profile directory with gateway port lifecycle.

First-principles alternative:

```text
AgentBinding
  user_id
  agent_template_id
  default_runtime_binding_id

HermesRuntimeState
  profile_slug
  profile_dir
  gateway_port

CliRuntimeState
  working_directory
  invocation_policy
  session_boundary
```

Do not make `profile_slug` the universal runtime identity. Make it Hermes-specific runtime state under a generic binding.

### 3. Funding and credential scope can become silent policy bugs

The planning says BYOK, company-pays, hybrid, delegated owner, and `user_only` no-fallback. That is necessary. The hard part is enforcement: every agent run must resolve exactly one payer and exactly one credential boundary before runtime execution. If this is left as UI state or profile config, delegated runs can accidentally use workspace fallback or the wrong user's key.

Safer invariant:

```text
Before execution:
  RunFundingDecision must be resolved and immutable.
  RunCredentialDecision must be resolved and immutable.
  If provider.user_only == true and user credential missing: fail closed.
  Runtime adapter receives only a lease/session handle, never policy choice authority.
```

### 4. Model catalog truth can drift across runtimes

Provider/model selection looks adapter-independent in the target model. That is only partly true. A Hermes-backed OpenRouter call, a Codex OAuth CLI session, a Claude CLI session, and a Cursor agent each expose different model catalogs, auth semantics, tools, streaming shape, and logs. A global model picker can overpromise.

Simpler alternative: model availability is computed from `(runtime_binding, provider_binding, funding_policy)` at selection time. The UI may show a general desired model, but the run gate must validate executable availability for that adapter.

### 5. Workspace boundary is more dangerous than provider boundary

Hermes Docker can be constrained to Workframe `Files/`. Host CLIs may default to the user's shell cwd, home directory, editor workspace, or cached project. If a host CLI adapter is ever launched without a strict cwd and filesystem policy, Workframe can leak or mutate files outside the cell.

Red-team rule: no host CLI adapter becomes executable until it proves:

- launch cwd is inside the Workframe cell or an explicitly selected project;
- writes are observable through run receipts;
- cancellation works;
- logs are captured without secrets;
- no host home is mounted or scanned by default;
- the user can see the exact workspace boundary before first run.

### 6. Receipts can become fake audit if they are only appended after success

The config pass correctly asks for run receipts. A receipt is useful only if it records intent before execution, transitions during execution, and terminal state after execution. If it is written only after a run succeeds, failed starts, wrong-payer decisions, partial writes, cancellations, and runtime crashes vanish.

Minimum receipt state machine:

```text
planned -> funding_resolved -> credential_lease_issued -> runtime_starting -> running -> terminal
terminal: succeeded | failed | cancelled | timed_out | policy_blocked
```

## Hidden complexity inventory

| Axis | Hidden complexity |
|---|---|
| Agent role | Templates, permissions, skills, UI defaults, prompt memory, run routing. |
| Runtime adapter | Start/stop, stream, cancel, logs, filesystem boundary, exit codes, retries, upgrades. |
| Provider/model | Catalog drift, unavailable models, provider-specific tool semantics, rate limits. |
| Funding | BYOK/company/hybrid, delegation, `user_only`, credit exhaustion, auditability. |
| Credential boundary | Vault lease vs external CLI session vs OAuth cache vs workspace key. |
| Workspace boundary | Docker mount vs host cwd vs editor workspace vs remote repository. |
| Run receipt | Pre-run decision, live status, terminal state, privacy redaction, billing evidence. |

## Security issues to pin before implementation

1. Do not give runtime adapters authority to choose payer or credential fallback.
2. Do not store raw CLI session paths, OAuth cache paths, account labels, or absolute host project paths in general run receipts.
3. Do not let host CLI adapters run from user home, repo parent directories, or ambiguous editor workspaces by default.
4. Do not show a model as selectable unless the selected runtime/provider/funding tuple can execute it.
5. Do not let company-pays mode override `user_only` providers or delegated-user ownership.
6. Do not conflate a successful provider lease with a successful runtime workspace boundary.
7. Do not implement multi-runtime UI controls before there is a harness that can fail them closed.

## Simpler first-principles alternative

```text
v0.1.x:
  - one executable runtime: hermes_docker_default
  - one workspace boundary: Workframe Files/
  - one enforceable run-funding resolver
  - one run receipt state machine
  - non-Hermes candidates hidden or diagnostic-only

v0.2:
  - generic AgentBinding schema introduced
  - Hermes-specific runtime state nested under the binding
  - provider/model/funding decisions validated before each run
  - no second executable adapter yet unless harness exists

v0.3:
  - one second adapter only
  - chosen by easiest full contract, not brand appeal
  - must pass start/stream/cancel/log/receipt/workspace/security tests
```

## Proposed migration / refactor steps

1. Amend planning doctrine so the first implementation target is not the full matrix; it is `HermesRuntimeBinding + FundingDecision + RunReceipt`.
2. Define `AgentBinding` separately from Hermes `profile_slug`; keep profile slug as Hermes adapter state, not universal identity.
3. Define `RunFundingDecision` and `RunCredentialDecision` as server-side pre-execution artifacts that runtime adapters cannot override.
4. Make model availability a derived validation result from runtime/provider/funding, not a static global picker.
5. Require workspace-boundary proof before any host CLI adapter becomes executable.
6. Add receipt states for policy-blocked, failed-start, cancelled, timed-out, and succeeded runs before adding a second adapter.
7. Keep non-Hermes candidates out of the primary wizard until the first second-adapter harness is green.

## Gaps / risks

- The planning rail may be overcorrecting from Hermes-coupling into adapter-generalization before the product has one stable, auditable run path.
- The term `profile` is doing too much: user identity, agent role, Hermes runtime state, provider binding, and billing boundary. This should be decomposed before non-Hermes adapters exist.
- The hardest security problem is not model choice; it is filesystem/workspace boundary for host CLIs.
- Funding policy must be resolved per run, not merely configured per team.
- Audit receipts need pre-run and failure states, or they will miss the incidents that matter most.

## Next best red-team target

Refactor map from Hermes-centered stack to adapter-first Workframe cell: challenge the smallest safe seam between current Hermes profile execution and future generic runtime bindings, with special attention to whether `profile_slug` should remain user-facing or become Hermes-internal state.
