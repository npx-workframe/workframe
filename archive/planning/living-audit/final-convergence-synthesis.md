# Final convergence synthesis — v0.1.x to v0.2

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
| Living audit index | `docs/living-audit/README.md` | `bcae35adef77b46c6774c9efbd075c2e0229b0ca` |
| Agent/runtime plan | `docs/living-audit/agent-runtime-config.md` | `9c6aa041be1c83d84165b54803db38ee32e48858` |
| Multi-user funding plan | `docs/living-audit/multi-user-provider-policy.md` | `7a02a4c87250458dc2826df6aaf63a9b91d24480` |
| Latest red team | `docs/living-audit/red-team-10-funding-authority-risk.md` | `ee12fbd969b145147e009b75dd32fc4ee978fea2` |
| Operator log | `operations/log.md` | `f9000a0d97b5e9c94adb5dcd843e518d02b3e6ca` |

## Planning slice

Final convergence synthesis: compress the installer, runtime detection, deployment order, adoption policy, surface baseline, funding policy, release gates, validation plan, and red-team findings into one first-principles roadmap from current repository state to the Workframe cell product.

## Current-state facts

- Public README currently describes Workframe as a multi-user web shell around Hermes with UI, API, installer, and Docker Compose.
- `START_HERE.md` treats product truth as the `create-workframe` npm pack and warns that dogfood green is not sign-off; the release path is pack, wipe sandbox, create-workframe, wizard, chat.
- Current package metadata is `0.1.7`; README install text still references `create-workframe@0.1.6`, so release-facing copy is version-drifted.
- Harness evidence is mostly cloud/API/build/scaffold oriented; UI bundle parity and full dogfood install-gate remain local/manual false scenarios.
- Current executable runtime is managed Hermes Docker. Host Hermes and other CLIs must remain off-limits or inert candidates until adapter harnesses exist.
- Prior planning established detection, adoption, deployment, surfaces, funding, and refactor seams, but no product code has been changed by this planning rail.
- Latest red-team pass reframes funding as pre-run credential authority, not post-run billing metadata.

## Target-state mapping

The product target should be expressed as a Workframe Cell:

```text
Workframe Cell
  -> shell: npx installer | Electron shell | VPS self-host
  -> manifest: identity, provenance, install mode, authority boundary
  -> surfaces: agent rail, chat, files, browser, activity first; kanban/goals/skills/slash/loops as declared contracts
  -> runtime bindings: managed Hermes executable first; host/CLI/cloud runtimes inert until validated
  -> provider bindings: user/workspace credential refs, redacted status, user_only invariant
  -> funding authority: BYOK/company/hybrid decision before invite/run
  -> run authority gate: actor, profile owner, runtime, provider, credential, payer, delegation authority
  -> receipt: minimum evidence for every allowed run
```

This keeps Hermes as the default starter runtime without making Hermes the product identity.

## Roadmap by proof layer

### Layer 0 — package truth gate for v0.1.x

Goal: make one destructive-new-install path credible before broadening the matrix.

Required gates:

```text
PackageTruthGate
  pack current package
  create clean sandbox
  run installer
  complete wizard
  confirm UI bundle parity
  confirm API/supervisor/Hermes health
  send first chat through managed Hermes Docker
  preserve source/package version agreement
  emit evidence artifact
```

Deferrals:

- no Electron-first setup claim
- no public/VPS launch claim beyond documented checklist
- no host-runtime adoption execution
- no second adapter execution
- no billing-grade accounting

### Layer 1 — cell authority and non-destructive open

Goal: prevent `open`, `update`, and `connect` from becoming hidden installers.

Required gates:

```text
CellAuthorityGate
  manifest exists
  manifest provenance is valid
  install root matches expected ownership
  data dirs are recognized
  destructive action requires explicit plan
  read-only open works before repair/update/connect
```

Default posture: `create` may create a new cell; `open` may inspect; `update/connect/adopt` remain gated until authority evidence is reliable.

### Layer 2 — mutation-free doctor / detection map

Goal: detect existing environments without reading secrets or changing host state.

Required outputs:

```text
workframe doctor --json
  detected_docker
  detected_node
  detected_workframe_cell
  detected_managed_hermes
  detected_host_hermes_redacted
  detected_cli_candidates: codex | claude | cursor | copilot | opencode | openclaw
  detected_provider_candidates_redacted
  forbidden_probe_attempts: none
  recommended_install_plan
```

Rule: detection records presence and readiness hints only. It never copies, rewrites, imports, or reads raw credential files.

### Layer 3 — surface contract gate

Goal: avoid claiming an operating system while panels lack authority/evidence semantics.

Minimum v0.1.x product spine:

```text
agent rail
chat
files
browser
activity
```

Each surface needs a small contract: what it reads, what it may mutate, which authority gate protects it, and what evidence is logged. Kanban, goals, skills, slash commands, loops, and audit should be shown only when their v0.1.x behavior is explicit and testable.

### Layer 4 — run authority and funding gate

Goal: make team execution safe before invites, delegation, loops, or company-pays claims.

Required model:

```text
RunAuthorityGate
  actor_user_id
  profile_owner_user_id
  run_context
  runtime_kind: managed_hermes for v0.1.x
  provider_kind
  provider_user_only
  workspace_funding_mode
  selected_binding_scope
  selected_payer_scope
  delegation_authority
  decision: allow | deny
  decision_reason
```

Policy simplification:

- `single_user_local`: BYOK only; actor equals profile owner; deny if no key.
- `trusted_team/public BYOK`: delegated execution requires explicit execute grant; assignment alone is not key access.
- `company_pays`: admin opt-in before invites; visible payer before run; only non-user-only LLM providers.
- `hybrid`: defer, or restrict to explicit fallback after receipt gate.

### Layer 5 — adapter-first v0.2 configuration

Goal: represent non-Hermes runtimes without executing them prematurely.

State machine:

```text
candidate_detected
  -> binding_declared
  -> adapter_harness_green
  -> executable_runtime
  -> first_run_verified
  -> selectable_default
```

Managed Hermes Docker starts as executable. Codex CLI, Claude CLI, Cursor, Copilot, OpenCode/OpenClaw, and host Hermes remain inert candidates until start/stream/cancel/log/receipt tests exist.

## Gaps / risks

- Version drift between README install command and package metadata is a direct release-trust issue.
- Current harness can pass while package/install/wizard/first-chat evidence is incomplete.
- Existing installer behavior risks destructive reruns unless manifest authority and read-only open semantics are formalized.
- Runtime detection can become privacy-invasive if it inspects token files instead of recording redacted readiness signals.
- Five-panel UI spine still crosses authority boundaries: file mutation, browser/session use, chat credentials, activity receipts, and agent profile control.
- BYOK, company-pays, hybrid, and delegation are currently distributed across docs; they need one pre-run authority decision before broad team use.
- Adapter-first language can overpromise if non-Hermes candidates appear executable before harness proof.

## Proposed migration / refactor steps

1. Treat `PackageTruthGate` as the next release blocker and produce a durable release-evidence artifact.
2. Fix release-facing version drift as part of release preparation, not as speculative architecture work.
3. Define `CellAuthorityGate` and make rerun/open/update/connect planning depend on it.
4. Specify `workframe doctor --json` as mutation-free preflight before adding installer adoption behavior.
5. Keep managed Hermes Docker as the only executable runtime in v0.1.x.
6. Move product language from "Hermes shell" toward "Workframe Cell with managed Hermes default" only after package truth is green.
7. Add a surface contract document or gate for agent rail/chat/files/browser/activity before expanding OS claims.
8. Define `RunAuthorityGate` and minimum run receipt before company-pays, hybrid fallback, delegated execution, or loops are marketed.
9. Represent non-Hermes runtimes as inert `RuntimeBinding` candidates until a second adapter passes start/stream/cancel/log/receipt validation.
10. Defer Electron-native setup, public multi-user hardening, quotas, billing, and executable host-CLI adoption until the gates above exist.

## Explicit deferrals

| Deferral | Reason |
|---|---|
| Electron owns setup | Needs a separate local authority model and host probe policy. |
| Host Hermes execution | Current doctrine says host Hermes is off-limits; adoption needs explicit consent and sandboxing. |
| Codex/Claude/Cursor execution | No adapter harness yet. |
| Hybrid funding default | Too many fallback paths before receipt/authority gate. |
| Public company-pays launch | Requires visible policy, quotas or at least payer banners, and no-fallback tests. |
| Full OS surface set | Kanban/goals/skills/slash/loops/audit need contracts before claims. |

## Next best planning target

Create a compact release decision memo: `v0.1.x PackageTruthGate checklist and evidence artifact schema`, using the release-readiness, installer-validation, red-team release-gate, and this synthesis as inputs.
