# Existing-runtime adoption policy

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
| Living audit index | `docs/living-audit/README.md` | `bcae35adef77b46c6774c9efbd075c2e0229b0ca` |
| Runtime detection plan | `docs/living-audit/runtime-detection-map.md` | `b18f34648656426d455e53f9db9ee391c55b9322` |
| Deployment order plan | `docs/living-audit/deployment-order.md` | `88c8105212bff0c2f2b7974826d63cce62f58e58` |
| Latest red-team pass | `docs/living-audit/red-team-07-open-update-connect-risk.md` | `6852963d984a88f4165e3fa14fe6be14d37720cf` |
| Operator log | `operations/log.md` | `737d40b8b85cfe849f38483b4c818c12d90f4236` |

## Planning slice

Existing-runtime adoption policy: define how Workframe should detect, display, consent to, and eventually bind host runtimes/CLIs/providers without overwriting user setups or pretending non-Hermes adapters are release-ready.

## Current-state facts

- The public entrypoint is still a Docker/Hermes scaffold path: README describes Workframe as a multi-user web shell around Hermes, and install docs say the end-user path is scaffold, Docker up, setup wizard, and launch.
- The installer package description is `Scaffold a Workframe + Hermes workspace with guided onboarding`; packaged files include API, UI, supervisor, scripts, profiles, and Hermes-oriented setup materials.
- Generated installs own `Agents/` and `Files/`, with `Agents/` mounted to `/opt/data` and `Files/` mounted under the Hermes/Workframe workspace boundary.
- `START_HERE.md` explicitly says host Hermes is off limits and Workframe Hermes is Docker `workframe-gateway`.
- Current architecture and session docs bind chat to Hermes profiles and sessions; per-user profiles are `u-{user}-{template}` and credentials are supposed to remain isolated through vault and lease behavior.
- Security docs establish BYOK default, `user_only` provider no-fallback behavior, supervisor separation, vault, and per-turn leases.
- Runtime detection planning already separates `DetectedRuntimeCandidate` from `ValidatedRuntimeAdapter`; only the latter may execute.
- The latest red-team pass narrows v0.1.x operations to supported create + read-only open, with update/connect/adoption deferred behind gates.

## Adoption vocabulary

| Term | Meaning | v0.1.x behavior |
|---|---|---|
| `host_tool_marker` | A locally detected CLI/app/runtime executable or marker. | Display as redacted hint only. |
| `host_auth_marker` | User-declared or safely inferred auth posture for a host tool. | `unknown` by default; never read token files. |
| `runtime_candidate` | A redacted, inert tool/running-service candidate in preflight output. | Not executable. |
| `managed_runtime` | Runtime state created and owned inside the Workframe cell. | Hermes Docker only for v0.1.x. |
| `adapter_binding` | User-consented binding from an agent profile to a validated adapter. | Planned only except Hermes binding. |
| `executable_adapter` | Adapter with start, stream, cancel, logs, receipt, and credential-boundary tests. | Hermes-in-Docker only. |

## Target-state mapping

### Branch 1 — local user already has Hermes plus Claude/Codex/etc.

```text
preflight detects host_tool_markers
  -> show redacted inventory
  -> create/open Workframe cell without touching host homes
  -> bind first agent to managed Hermes Docker
  -> offer future adapter candidates as disabled choices
```

Policy: host Hermes can be recognized but must not be mounted, copied, or used as Workframe state. Claude/Codex/Cursor/Copilot/OpenCode markers are UI hints until adapter validation exists.

### Branch 2 — Docker user has no Hermes but has provider auth

```text
provider posture present/declared
  -> not runtime-ready
  -> create managed Docker/Hermes cell
  -> connect provider through Workframe-owned vault / lease path
  -> first chat proves managed runtime + provider path
```

Policy: provider auth is not a runtime. Do not treat OpenAI/Codex auth as executable until a runtime adapter can start, stream, cancel, and receipt.

### Branch 3 — user has nothing installed

```text
missing runtime + missing provider
  -> recommend managed Docker/Hermes default
  -> block first agent run until BYOK/company provider is configured
  -> surfaces may launch with runtime-dependent actions disabled
```

Policy: Workframe product identity stays the cell/shell/surfaces; Hermes is the default managed runtime, not the product boundary.

### Branch 4 — VPS/self-hosted team

```text
public/team mode
  -> ignore local host_tool_markers for server runtime decisions
  -> require domain/HTTPS/SMTP/secrets/invite policy
  -> managed runtime lives on the server cell
  -> local Electron/CLI can connect only as a client
```

Policy: local CLI detection must never be auto-applied to a remote cell. A remote cell has its own runtime inventory and credential boundary.

### Branch 5 — multi-user funding

```text
agent run request
  -> resolve actor, assignee agent, workspace, funding policy
  -> user_only providers never fall back to workspace creds
  -> company-pays requires explicit admin opt-in
  -> every run writes a funding decision/receipt
```

Policy: funding cannot be inferred from which CLI exists. It must be part of profile/run policy.

## Adoption state machine

```text
UNSEEN
  -> DETECTED_REDACTED       # marker-only, no auth/file reads
  -> USER_CONFIRMED          # user says this tool exists / wants it considered
  -> CAPABILITY_PROBED       # safe version/help only, no login mutation
  -> ADAPTER_VALIDATED       # harness proves start/stream/cancel/log/receipt
  -> BOUND_TO_AGENT_PROFILE  # explicit user/admin consent
  -> EXECUTABLE              # runtime can receive runs
```

Forbidden shortcuts:

```text
DETECTED_REDACTED -> EXECUTABLE
HOST_HERMES -> MANAGED_RUNTIME
PROVIDER_AUTH -> RUNTIME_READY
OPEN_EXISTING_CELL -> SILENT_ADOPTION
CONNECT_REMOTE_CELL -> LOCAL_RUNTIME_BINDING
```

## Capability and consent matrix

| Asset | Detect? | Display? | Deep probe? | Adopt? | Execute in v0.1.x? | Hard rule |
|---|---:|---:|---:|---:|---:|---|
| Workframe-managed Hermes Docker | Yes | Yes | Yes | Already managed | Yes | Only supported executable runtime. |
| Host Hermes home | Marker only | Redacted | Only after explicit local consent | No by default | No | Never mount/copy host Hermes. |
| Claude CLI | Executable marker | Redacted | Version/help only | Later | No | Do not read auth/cache/history. |
| Codex/OpenAI CLI | Executable marker | Redacted | Version/help only | Later | No | Auth posture is not runtime readiness. |
| Cursor app/CLI | Marker only | Redacted | Version/help if CLI exists | Later | No | Do not scrape workspace/session state. |
| Copilot/GitHub auth | Provider marker | Redacted | User-declared or OAuth flow | Provider only | No | `user_only`, no workspace fallback. |
| OpenCode/OpenClaw | Executable marker | Redacted | Version/help only | Later | No | Naming/version ambiguity must not imply support. |
| Provider env vars | Workframe-owned only | Boolean only | No raw value | Provider setup path | No | Never print/import secrets. |
| Docker images/containers | Workframe labels only by default | Yes | Docker inspect only for owned labels | Managed if Workframe-owned | Hermes only | Do not adopt arbitrary containers. |

## Gaps / risks

- Current installer code has a `detectHermesHome` seam and deploy-mode vocabulary, but adoption planning requires marker-only detection to be separated from deploy selection.
- Current public wording remains Hermes-centered. This is acceptable for v0.1.x release truth, but the plan must avoid making Hermes the permanent ontology.
- Existing host tools can leak sensitive context through paths, account names, workspace names, container names, and profile names even without reading token values.
- Electron can accidentally blur local host-tool inventory with a remote VPS cell; the UI must show whether detection is local-client or remote-cell.
- Provider credentials and CLI sessions have different trust boundaries. A local CLI auth session may be usable by a human but still unsafe for a server-side multi-user Workframe run.
- Multi-user adoption of host-local CLIs is mostly a category error: team cells need server-managed runtimes or per-user BYOK/leases, not one user’s local CLI session.
- Adapter-first ambition can overwhelm the next release. The safest path is to keep Hermes as the only executable runtime while designing adapter data shapes now.

## Proposed migration / refactor steps

1. Define `RuntimeInventoryReport` as a transient, redacted preflight output; do not persist it as authority until redaction gates exist.
2. Split `host_tool_marker`, `managed_runtime`, and `adapter_binding` in docs before adding implementation.
3. Keep `managed_hermes_docker` as the only v0.1.x executable runtime.
4. Add a no-host-adoption rule to the installer decision tree: detected host runtimes never change scaffold output.
5. Add consent screens later with two separate verbs: `consider this tool` and `bind this tool to an agent`; never combine them.
6. Require an adapter harness before any non-Hermes runtime can be selected by an agent profile.
7. Require run receipts to record runtime, provider policy, funding source, credential boundary, and execution boundary.
8. For remote/Electron, make inventory scoped: `local_client_inventory` versus `remote_cell_inventory`.
9. Add fixture tests before implementation: fake host Hermes, fake Claude CLI, fake Codex auth marker, existing Workframe cell, remote connect path, and no-write assertions.

## Minimal v0.1.x policy

```text
Supported:
  - create new local/Docker Workframe cell
  - open existing Workframe cell read-only
  - execute managed Hermes Docker runtime
  - connect providers through Workframe-owned setup flows

Displayed but inert:
  - host Hermes
  - Claude CLI
  - Codex/OpenAI CLI
  - Cursor
  - Copilot/GitHub auth posture
  - OpenCode/OpenClaw
  - arbitrary provider/environment hints

Deferred:
  - host runtime adoption
  - non-Hermes executable adapters
  - update/migration of existing cells
  - local runtime binding into remote cells
```

## Open questions for later passes

- Should adapter candidates ever be persisted in `workframe-manifest.json`, or should they remain transient until bound to an agent profile?
- Which adapter should be validated second after Hermes: Codex CLI, Claude CLI, Cursor, or OpenCode/OpenClaw?
- What is the safest consent UX for a local-only single-user cell versus a public multi-user cell?
- Should host Hermes adoption stay permanently unsupported, or only unsupported until a read-only import/export bridge exists?
- Which fields belong in a run receipt before billing-grade funding is implemented?

## Next best planning target

Workframe surface baseline: define the minimum files/browser/activity/kanban/goals/skills/slash-command/loops/agents/runs/audit experience that works even when only managed Hermes is executable and all other runtimes are inert candidates.
