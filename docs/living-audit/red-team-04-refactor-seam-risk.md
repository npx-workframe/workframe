# Red team 04 — adapter seam and profile identity risk

Temporary living-audit planning material. Not public release doctrine. Planning only; no product source-code changes are implied by this file.

## Inspected ref / SHAs

Repository resolved directly: `npx-workframe/workframe`, default branch `main`.

| Area | Path | Blob SHA |
|---|---|---|
| Refactor planning pass | `docs/living-audit/refactor-map.md` | `5f8b28d129fa32320072371b8f260e2cfed87385` |
| Runtime detection pass | `docs/living-audit/runtime-detection-map.md` | `b18f34648656426d455e53f9db9ee391c55b9322` |
| Agent runtime config pass | `docs/living-audit/agent-runtime-config.md` | `9c6aa041be1c83d84165b54803db38ee32e48858` |
| Prior red team pass | `docs/living-audit/red-team-03-agent-runtime-matrix.md` | `203a5f577f3d5133c0d10193f8167f065f1215d8` |
| Supervisor source | `services/workframe-supervisor/server.py` | `2ffcbfd84da421f59b62bb371f08fc727b560f70` |
| API source | `services/workframe-api/server.py` | `52e962760c28ad0eb70240287ed49aa746d3767b` |
| Installer source | `packages/create-workframe/bin/create-workframe.js` | `3983e3e5e9110f406ab0f7a5d238a34c00c066f0` |
| Operator log | `operations/log.md` | `7c1576c10dc8f7bc667f9a73f0e871ad78baebb7` |

## Planning slice challenged

Adversarial review of `refactor-map.md`: whether the proposed Hermes-centered to adapter-first seam is small enough to be implemented safely, or whether it creates hidden identity, security, and product-surface contradictions before the current Hermes path is stable and auditable.

## Current-state facts

- The refactor pass correctly says the target path should be `UI room/session -> API agent_profile_id -> RuntimeBinding(kind=hermes) -> HermesAdapter -> stream + receipt`.
- The current API still describes itself as a fast Hermes-native backend and reads Hermes stores directly: `state.db`, `kanban.db`, `gateway_state.json`, and `cron/jobs.json`.
- The current API defines `ROUTES_JSON`, `AGENTS_JSON`, avatar registries, lane registry, `HERMES_DATA`, `WORKSPACE`, `DOCKER_SOCK`, gateway container name, and supervisor URL in one server process.
- The current supervisor is explicitly a token-gated Docker exec service for Hermes profile lifecycle and controls Docker compose, Hermes profile auth, gateway image identity, public HTTPS host setup, and stack updates.
- The current installer writes Hermes-flavored `routes.json`, mounts `Agents/` into `/opt/data`, mounts `Files/` into the Hermes workspace path, creates a gateway command around `HERMES_HOME`, and binds the supervisor to the Docker socket.
- Public overlay removes API docker.sock access, but the supervisor remains privileged and still owns Docker socket and host/project mutation authority.
- The prior red-team pass already found that the full role/runtime/provider/funding matrix is too broad for the next implementation and should collapse to `HermesRuntimeBinding + FundingDecision + RunReceipt` first.

## Red-team contradictions / weak assumptions

### 1. `HermesAdapter` is not just a wrapper; it is most of the product runtime today

The refactor map treats Hermes wrapping as a naming seam. In the code, Hermes assumptions are not isolated to one boundary. They appear in installer-generated compose, API data paths, session access, supervisor lifecycle, dashboard auth, profile homes, workspace mounts, routes, and public setup scripts.

Risk: adding `RuntimeBinding` names without shrinking these dependencies creates a false abstraction. The code would look adapter-first while still behaving Hermes-first everywhere important.

Simpler rule: do not introduce a generic adapter registry until the current Hermes-specific dependencies are listed as an explicit compatibility surface.

### 2. `profile_slug` should not remain user-facing adapter vocabulary

The refactor map says `profile_slug` is still valid but no longer equal to runtime identity. That is a transitional compromise, but it may leak into UI/API contracts and become permanent. The installer currently writes route objects where `id`, `profile`, channel id, display name, and role are all tied to the same Hermes profile string.

First-principles alternative:

```text
AgentIdentity
  stable user-facing agent id
  role/template
  display name

RuntimeBinding
  binding id
  runtime kind
  executable state

HermesRuntimeState
  profile_slug
  profile_dir
  gateway_port
  route cache entry
```

User-facing surfaces should speak in terms of agents and runs, not Hermes profile slugs. `profile_slug` should become Hermes adapter state, not product identity.

### 3. The adapter contract is missing the two hard methods: `prepare_workspace` and `preflight_policy`

The proposed adapter contract lists `detect`, `validate`, `start`, `stream`, `cancel`, `status`, `logs`, and `receipt_fields`. That misses two operations that decide whether an adapter is safe:

```text
preflight_policy(run_request) -> allow | block + reason
prepare_workspace(run_request) -> exact cwd/mount/project boundary
```

Without these, a host CLI adapter can pass start/stream/cancel/log tests while still reading or writing the wrong filesystem, using an external session silently, or bypassing funding policy.

### 4. Run receipts cannot be adapter-owned

The refactor map asks adapters to provide `receipt_fields`. That is necessary but dangerous if the adapter becomes the source of truth for payer, credential boundary, workspace boundary, or validation state. Runtime adapters are execution mechanisms; they must not decide policy.

Safer split:

```text
Server-owned before execution:
  RunIntent
  FundingDecision
  CredentialDecision
  WorkspaceDecision
  PolicyDecision

Adapter-owned during/after execution:
  runtime process id/session id
  stream status
  logs handle
  terminal status
  runtime-specific diagnostics
```

A receipt should start before adapter invocation. Adapter data should enrich it, not create it.

### 5. Public setup is a separate risk axis, not part of adapter abstraction

The supervisor can launch a privileged Debian container with host PID namespace and `/` mounted into `/host` to run public HTTPS setup. This is not an adapter concern. It is an installer/admin-operation concern with a different threat model from agent runtime execution.

Risk: if adapter-first refactor pulls supervisor responsibilities into a generic runtime manager, it may accidentally normalize privileged host mutation as a runtime capability.

Rule: split `AdminHostOperations` from `RuntimeAdapter`. A runtime adapter should not own domain, HTTPS, compose mutation, package update, or host chroot tasks.

### 6. `routes.json` compatibility may still block adapter-first behavior

The refactor pass correctly warns not to overload `routes.json` as adapter authority. The deeper risk is that current UI/API behavior may already depend on `routes.json` as agent truth. If so, creating a separate adapter registry can introduce two truths unless one side is clearly derived.

Simpler rule: for v0.1.x, treat `routes.json` as generated Hermes compatibility output from canonical `AgentIdentity + HermesRuntimeState`, not as user-authored product config.

## Hidden complexity inventory

| Seam | Hidden risk |
|---|---|
| API server | Mixes UI API, Hermes state reads, provider proxy, files, auth, sessions, install API, and action proxy in one process. |
| Supervisor | Mixes runtime lifecycle, Docker control, profile auth, public HTTPS, stack updates, and host mutation. |
| Installer | Generates runtime, UI, API, supervisor, scripts, routes, compose, public overlay, ports, and workspace mounts together. |
| Routes | Currently acts as Hermes routing cache and apparent agent catalog. |
| Workspace | `Files/` is safe for Hermes Docker, but host CLI adapters need a different boundary proof. |
| Receipts | Must record failed starts and policy blocks, not only successful streams. |
| Public mode | Security posture depends on API not having docker.sock, but supervisor remains powerful by design. |

## Security issues to pin before implementation

1. Do not let `RuntimeAdapter` include public HTTPS, compose update, host chroot, package update, or Docker socket administration.
2. Do not let adapters decide payer, credential fallback, workspace scope, or public launch readiness.
3. Do not expose `profile_slug`, profile directory, gateway port, or host paths as stable public product identifiers.
4. Do not create a second canonical agent registry unless `routes.json` becomes derived compatibility output or is explicitly deprecated.
5. Do not let host CLI adapter tests pass without `prepare_workspace` proof and workspace-boundary UI disclosure.
6. Do not write receipts only after streaming succeeds; policy-blocked and failed-start runs are the audit-critical cases.
7. Do not let public VPS/admin operations share the same abstraction as per-run agent execution.

## Simpler first-principles alternative

```text
v0.1.x convergence target:
  AgentIdentity -> HermesRuntimeState -> Hermes execution
  Server-owned RunIntent/FundingDecision/CredentialDecision/WorkspaceDecision
  Receipt state machine begins before execution
  routes.json remains generated Hermes compatibility cache
  no generic AdapterRegistry UI
  no second executable runtime

v0.2 seam target:
  Extract AdminHostOperations away from runtime lifecycle
  Extract HermesRuntimeState away from AgentIdentity
  Extract RunPolicyResolver before runtime call
  Define RuntimeAdapter only around execution: preflight_policy, prepare_workspace, start, stream, cancel, logs, terminal diagnostics

v0.3 expansion target:
  Add one second adapter only after it proves workspace boundary, credential boundary, cancel, logs, receipts, and failure states
```

## Proposed migration / refactor steps

1. Amend the refactor map so the first code seam is not `AdapterRegistry`; it is `AgentIdentity` separated from `HermesRuntimeState`.
2. Define `RunPolicyResolver` as server-owned pre-execution state: funding, credential, workspace, model availability, and policy block reason.
3. Define receipt lifecycle before runtime invocation: `planned -> policy_resolved -> credential_ready -> workspace_ready -> runtime_starting -> running -> terminal`.
4. Split supervisor responsibilities in the plan into `HermesRuntimeSupervisor` and `AdminHostOperations`; only the former belongs near runtime adapters.
5. Treat `routes.json` as generated Hermes compatibility cache, not adapter registry or canonical agent catalog.
6. Add `preflight_policy` and `prepare_workspace` to the future adapter contract before any second adapter proof.
7. Keep the UI focused on one executable Hermes path until agent identity, policy resolver, receipt lifecycle, and workspace boundary are explicit.

## Gaps / risks

- The current planning may underestimate how much of the product is still Hermes-shaped: API data paths, route cache, supervisor lifecycle, dashboard, compose, and installer all encode it.
- A generic adapter registry could become a cosmetic abstraction if Hermes-specific state is not first isolated.
- The highest-risk refactor seam is not streaming; it is policy resolution before runtime execution.
- Host/admin operations and runtime execution are currently adjacent through the supervisor. They should be separated conceptually before implementation.
- Public mode security should not be evaluated through adapter abstractions; it needs its own launch gate and admin-operation audit.

## Next best red-team target

Release-readiness blockers: challenge whether the living-audit maps imply any release can be cut before doc/version drift, destructive install gates, public launch gates, receipt lifecycle, and Hermes identity decomposition are resolved.
