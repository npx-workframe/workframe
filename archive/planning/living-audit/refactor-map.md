# Refactor map — Hermes-centered stack to adapter-first Workframe cell

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
| Installer | `packages/create-workframe/bin/create-workframe.js` | `3983e3e5e9110f406ab0f7a5d238a34c00c066f0` |
| Installer identity helper | `packages/create-workframe/scripts/lib/install-identity.mjs` | `e2ceb2356b6112bbfec90520b0c60cd7212e825b` |
| API | `services/workframe-api/server.py` | `52e962760c28ad0eb70240287ed49aa746d3767b` |
| Supervisor | `services/workframe-supervisor/server.py` | `2ffcbfd84da421f59b62bb371f08fc727b560f70` |
| Prior decision tree | `docs/living-audit/README.md` | `bcae35adef77b46c6774c9efbd075c2e0229b0ca` |
| Prior detection pass | `docs/living-audit/runtime-detection-map.md` | `b18f34648656426d455e53f9db9ee391c55b9322` |
| Prior config pass | `docs/living-audit/agent-runtime-config.md` | `9c6aa041be1c83d84165b54803db38ee32e48858` |

## Planning slice

Refactor map from current Hermes-centered stack to adapter-first Workframe cell: identify minimal seams where `profile_slug == runtime` can become `runtime_binding -> execution adapter` without changing current runtime behavior.

## Current-state facts

- Public identity still says Workframe is a multi-user web shell around Hermes, and install docs route users through `npx create-workframe@0.1.6`, Docker compose, and first-boot wizard.
- Package metadata is `0.1.7`, while public README/install docs still advertise `0.1.6`.
- Generated installs currently ship API, UI, supervisor, `Agents/`, `Files/`, compose, and a manifest-like generated layout.
- The installer package is explicitly `Workframe + Hermes`; it pulls/runs the Hermes Docker image, creates Hermes profiles, writes `Agents/workframe/routes.json`, and treats bare Hermes default profile as not a Workframe install.
- Architecture and session docs bind UI/API chat to Hermes profiles and Hermes state; per-user runtime identity is documented as `u-{user}-{template}`.
- API source already centralizes many future seams: `ROUTES_JSON`, `AGENTS_JSON`, `lane-registry.json`, room/session binding, credential vault, provider proxy, turn leases, install mode, and deployment mode.
- Supervisor source is the strongest Hermes-coupled seam: it manages Docker exec, Hermes profile lifecycle, profile paths, gateway ports, and credential-path guards.
- Harness coverage is strong for current Hermes/Docker/API/UI/scaffold path but does not cover adapter registry, non-Hermes runtime contracts, detection reports, or run receipts.

## Target-state mapping

The adapter-first cell should not replace Hermes immediately. It should wrap the existing path as the first validated adapter.

```text
Current executable path
  UI room/session -> API profile_slug -> Hermes gateway/profile -> stream

Target abstraction path
  UI room/session -> API agent_profile_id -> RuntimeBinding(kind=hermes) -> HermesAdapter -> stream + receipt
```

Minimum target vocabulary:

| Concept | Current equivalent | Target meaning |
|---|---|---|
| `profile_slug` | Hermes profile and user runtime identity | Still valid, but no longer equal to runtime identity. |
| `RuntimeBinding` | Implicit Docker Hermes profile route | Selected execution backend plus capability contract. |
| `HermesAdapter` | Existing gateway/supervisor/profile code | First and only executable adapter until another harness is green. |
| `ProviderBindingPolicy` | Vault + provider model selection + lease | Provider/model/credential/fallback policy independent of runtime. |
| `RunReceipt` | Partial logs/state/session rows | Audit record tying agent, runtime, provider, model, payer, scope, and result. |
| `AdapterRegistry` | None; routes are Hermes routes | Cell-owned registry of executable and inert runtime candidates. |

## Refactor seams

| Seam | Current owner | Adapter-first direction | Rule |
|---|---|---|---|
| Install preflight | Installer identity helper | `preflight_report -> install_plan -> confirm -> mutation` | Detection never mutates. |
| Generated manifest | Installer | Add adapter/funding/provider declarations later | Manifest is metadata, not secret storage. |
| Routes | `Agents/workframe/routes.json` | Keep as Hermes route cache; introduce cell adapter registry separately | Do not overload routes as adapter authority. |
| Room/session binding | API `room_sessions` + Hermes state | Bind to agent profile, then resolve runtime binding | Preserve current Hermes session behavior. |
| Credential access | Vault, turn leases, LLM proxy | Keep vault leases as first-class provider boundary | No runtime gets raw workspace fallback implicitly. |
| Profile lifecycle | Supervisor | Wrap as `HermesAdapter.start/stop/status` | Other adapters must not inherit Docker/Hermes assumptions. |
| Gateway streaming | API to Hermes HTTP | Adapter stream interface | Keep Hermes as compatibility implementation. |
| Logs/audit | Hermes state + API records | Run receipt ledger | Receipt before billing/platform claims. |
| UI model/runtime picker | Current provider/model surfaces | Display only validated choices by default | Inert candidates stay behind disclosure. |

## Gaps / risks

- If adapter work starts inside the monolithic installer, detection, planning, mutation, and runtime execution will become coupled and brittle.
- If `routes.json` becomes the adapter registry, Hermes routing cache will become product doctrine and block non-Hermes runtimes.
- If non-Hermes CLIs are forced into Hermes profile semantics, their security boundaries, workspace roots, cancellation model, logs, and auth posture will be misrepresented.
- If run receipts are deferred, company-pays, hybrid funding, delegated runs, and public audit will remain unverifiable.
- If the UI exposes all detected CLIs as selectable runtimes before harness validation, first-run UX will look powerful but fail at execution.
- If Electron owns local detection while Docker/API owns server detection, the product can report contradictory host/runtime posture unless they share one schema.

## Proposed migration / refactor steps

1. Keep the current Hermes Docker path as `RuntimeBinding(kind=hermes, adapter=hermes_docker, executable=true)` in planning docs before code changes.
2. Define the adapter contract before adding adapters: `detect`, `validate`, `start`, `stream`, `cancel`, `status`, `logs`, `receipt_fields`.
3. Define a small `RunReceipt` schema before expanding runtime options: run id, user id, agent profile id, runtime binding id, provider, model, payer, workspace boundary, credential boundary, started/ended status, error class.
4. Split the install path conceptually into four modules: preflight report, install plan, mutation executor, validation gate.
5. Keep `Agents/workframe/routes.json` as Hermes compatibility routing; introduce adapter registry as separate cell metadata after schema review.
6. Wrap existing supervisor/profile lifecycle under a Hermes adapter boundary; do not change behavior while introducing names.
7. Add harness fixtures for adapter registry inertness, Hermes compatibility, run receipt completeness, and no-fallback provider policy before implementing a second adapter.
8. Only after Hermes is wrapped and receipts exist, select one second adapter for a narrow proof: start, stream one response, cancel, collect logs, write receipt.

## Validation gates for this slice

| Gate | Evidence required |
|---|---|
| No behavior change | Existing Hermes first-chat and scaffold tests still pass after future seam introduction. |
| No route overload | `routes.json` remains compatible with existing UI and is not the canonical adapter registry. |
| Runtime/provider separation | Provider/model policy can change without rewriting runtime binding. |
| Runtime/profile separation | A user agent profile can point to Hermes now and another adapter later without changing agent identity. |
| Receipt completeness | Every executable runtime path can produce the minimum receipt fields. |
| Non-Hermes inertness | Detected CLIs cannot execute until adapter validation gates pass. |
| Public safety | Public/VPS launch gate remains separate from local runtime health. |

## Open questions for later passes

- Should adapter registry canonical state live in API DB first, `workframe-manifest.json` first, or both with one source of authority?
- What is the minimum UI copy that avoids making Hermes look like the product identity while still being honest that Hermes is the only executable v0.1.x runtime?
- Which second adapter has the cleanest proof path after Hermes wrapping: Codex CLI, Claude CLI, Cursor, OpenCode/OpenClaw, or Copilot?
- Should run receipts live in API DB, `Agents/workframe`, or both exported from one canonical ledger?

## Next best planning target

Release-readiness blockers: convert the living-audit maps into a strict list of blockers for the next package release, separating doc drift, harness gaps, installer safety gates, public launch gates, and adapter-first deferrals.
