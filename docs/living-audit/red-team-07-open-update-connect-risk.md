# Red team 07 — open/update/connect path and hidden second-installer risk

Temporary living-audit planning material. Not public release doctrine. Planning only; no product source-code changes are implied by this file.

## Inspected ref / SHAs

Repository resolved directly: `npx-workframe/workframe`, default branch `main`.

| Area | Path | Blob SHA |
|---|---|---|
| Entry | `README.md` | `b97cd64e4f899dc758bb73a0e04ec9a89a344317` |
| Agent rules | `AGENTS.md` | `f648f29fdb9569c3bb7a5c6c8e178173582cde03` |
| Repo map | `START_HERE.md` | `cf65246dc937256099d8297e79487635c3b724d2` |
| Living audit index | `docs/living-audit/README.md` | `bcae35adef77b46c6774c9efbd075c2e0229b0ca` |
| Runtime detection map | `docs/living-audit/runtime-detection-map.md` | `b18f34648656426d455e53f9db9ee391c55b9322` |
| Refactor seam red team | `docs/living-audit/red-team-04-refactor-seam-risk.md` | `a5f8576d6784f50c6a02f3482befa33ec76bc86a` |
| Release gate red team | `docs/living-audit/red-team-05-release-gate-risk.md` | `da5b40e246e7a2732decd4b295c4fbf08e6a2ed9` |
| Validation matrix red team | `docs/living-audit/red-team-06-validation-matrix-risk.md` | `3968385e4685f419751f8217c1d384303bb10308` |
| Deployment order planning | `docs/living-audit/deployment-order.md` | `88c8105212bff0c2f2b7974826d63cce62f58e58` |
| Operator log | `operations/log.md` | `3e5e23d009dca75119485250f5d2448c08eb8710` |

## Planning slice challenged

Adversarial review of `deployment-order.md`: whether the proposed `create/open/update/connect` state machine actually reduces installer risk, or whether `open`, `update`, and `connect` become untested mutation paths that bypass the package truth gate.

## Current-state facts

- The repo itself says Workframe is currently a `create-workframe` npm pack and a Hermes-backed collaboration layer, with UI, API, installer, Docker Compose, and supervisor surfaces.
- Repo instructions require source artifacts over memory, read-before-write mutation discipline, and smallest coherent changes.
- `START_HERE.md` distinguishes source, dogfood local, dogfood VPS, and host Hermes; host Hermes is explicitly off limits and Workframe Hermes is Docker `workframe-gateway`.
- `START_HERE.md` says package sign-off is pack, wipe sandbox, `create-workframe`, wizard, chat; dogfood green alone is not sign-off.
- The runtime detection plan correctly says detection is not adoption, host runtime homes are never mounted/copied/modified by default, and non-Hermes CLIs stay inert until adapter validation exists.
- The deployment-order pass proposes four verbs: `create_new_cell`, `open_existing_cell`, `update_existing_cell`, and `connect_remote_cell`.
- The latest red-team pass narrowed next release truth to `PackageTruthGate` and made existing-target sentinel refusal release-critical.

## Red-team contradictions / weak assumptions

### 1. Four verbs can create four untested products

`create/open/update/connect` is the right user vocabulary, but it is dangerous if each verb grows its own implementation path. The next release must not create a second installer under the names `open` or `update`.

Simpler rule:

```text
create = only mutating scaffold path for v0.1.x
open   = read manifest + health/status only
update = blocked unless backup + artifact provenance + rollback gate exist
connect = remote session selector only; no local scaffold mutation
```

Anything else turns the state machine into four partially tested installers.

### 2. `open_existing_cell` can become silent migration

Opening an existing folder sounds harmless, but it can easily drift into repair, re-render, compose rewrite, env normalization, route regeneration, profile creation, or UI bundle refresh. Those are migrations, not open operations.

Hard boundary:

```text
open_existing_cell may read:
  manifest, compose presence, health endpoints, public-safe status booleans

open_existing_cell must not write:
  .env, compose files, Agents/, Files/, routes.json, vault, API db, package bundle
```

If a write is required, the UI should emit `needs_update` with a dry-run plan, not perform repair.

### 3. `update_existing_cell` is more dangerous than first install

A clean install can be wiped and retried. An existing cell has user data, vault records, profiles, files, possibly team invites, and runtime state. The planning rail treats update as one state among four, but update is the only state that can destroy real business memory.

Minimum update gate before implementation:

```text
UpdateGate
  source_package_identity
  target_manifest_identity
  backup_created_and_verified
  migration_plan_dry_run
  data_paths_touched
  rollback_plan
  post_update_health
```

Without this, v0.1.x should say: create and open are supported; update is manual or blocked.

### 4. `connect_remote_cell` can blur trust boundaries

Electron or local CLI connecting to a VPS must not inherit local authority. A desktop shell can accidentally make a remote cell feel local and hide whether commands run on the user's machine, the VPS, or inside Hermes workspace.

Connect must display:

```text
cell_identity
remote_url
owner/admin identity
current user role
execution boundary: local | remote_vps | docker_cell
credential boundary: local_session | remote_vault | unknown
```

No runtime detection from the local machine should be auto-applied to the remote cell.

### 5. Manifest identity is under-specified

The deployment state machine depends on recognizing an existing Workframe cell, but the audit does not yet define the manifest as an authority. If detection relies on folder names, compose file names, or `Agents/` presence, it risks false positives and overwrites.

Minimum manifest authority:

```text
workframe_manifest_version
cell_id
created_by_package
created_from_source_commit_or_package
install_mode
data_paths
managed_runtime_paths
public_mode_declared
last_successful_package_gate_reference
```

The manifest should identify ownership; it should not store secrets or claim current public readiness.

### 6. Adoption policy must not ride on open/update

The target product wants to adopt Hermes, Claude CLI, Codex, Cursor, Copilot, and other runtimes. The safe place for that is a preflight candidate report and later explicit adapter consent, not `open_existing_cell` or `update_existing_cell`.

Rule: opening an existing Workframe cell can show external runtimes as host-local hints only when the preflight report is local and redacted. It must not bind them to the cell.

## Hidden complexity inventory

| Verb | Hidden failure mode | Safer v0.1.x posture |
|---|---|---|
| `create` | Existing target overwritten by scaffold behavior | Require absent target or explicit destructive wipe verb plus sentinel proof. |
| `open` | Silent repair/migration rewrites user state | Read-only manifest and health/status; emit dry-run plan only. |
| `update` | Real user data/vault/routes/profile state corrupted | Block until backup, dry-run migration, rollback, and artifact provenance exist. |
| `connect` | Desktop/local context confused with remote execution context | Remote identity and execution boundary shown before action. |
| `detect` | Local CLI/provider posture leaks or binds into remote cell | Redacted local-only candidate report; no automatic adoption. |

## Simpler first-principles alternative

For the next credible release, collapse the verb set into two real operations and two deferred shells:

```text
Supported now:
  create_new_local_docker_hermes_cell
  open_existing_cell_read_only

Deferred / blocked until gates exist:
  update_existing_cell
  connect_remote_cell
  adopt_external_runtime
```

This is less ambitious but safer. It preserves the Softsupply/product direction without letting install UX outrun evidence.

## Security issues to pin before implementation

1. Do not let `open` write anything until a read-only open gate exists.
2. Do not let `update` exist as a convenience alias for rerunning installer scripts.
3. Do not let Electron hide whether execution is local, remote, or Docker-contained.
4. Do not use host Hermes, Claude, Codex, Cursor, Copilot, or OpenCode detection to mutate a cell.
5. Do not treat folder shape as Workframe ownership; require a manifest authority.
6. Do not persist public-ready booleans in the manifest; persist evidence references and timestamps only.
7. Do not allow package release evidence to skip an existing-target sentinel refusal test.

## Proposed migration / refactor steps

1. Define `workframe-manifest.json` authority before implementing open/update/connect behavior.
2. Make `open_existing_cell` explicitly read-only in planning language and future tests.
3. Split `update_existing_cell` out of v0.1.x release claims unless `UpdateGate` exists.
4. Define `connect_remote_cell` as an identity/session boundary screen before any Electron installer work.
5. Keep runtime adoption as a separate `PreflightCandidate -> ExplicitConsent -> AdapterValidation` path.
6. Add four named negative tests to planning: no open writes, no update without backup, no local-runtime binding to remote cell, no folder-shape ownership.

## Next best planning target

Existing-runtime adoption policy: specify the difference between detected host tools, user-consented runtime candidates, managed Workframe runtimes, and executable adapters without implementing non-Hermes execution yet.
