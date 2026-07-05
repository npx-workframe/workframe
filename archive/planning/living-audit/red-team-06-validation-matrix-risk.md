# Red team 06 — validation matrix and evidence inflation risk

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
| Agent runtime config | `docs/living-audit/agent-runtime-config.md` | `9c6aa041be1c83d84165b54803db38ee32e48858` |
| Refactor map | `docs/living-audit/refactor-map.md` | `5f8b28d129fa32320072371b8f260e2cfed87385` |
| Release readiness | `docs/living-audit/release-readiness.md` | `3581c625be86e5e1fd7208c687c75af99115ea6d` |
| Installer validation plan | `docs/living-audit/installer-validation-plan.md` | `cf2b297851d0f6b0c4f8726984b9ae8b70f1fb8f` |
| Prior red-team pass | `docs/living-audit/red-team-05-release-gate-risk.md` | `da5b40e246e7a2732decd4b295c4fbf08e6a2ed9` |
| Operator log | `operations/log.md` | `572f3efefd6f968c7c1fafef512ea2662f041a15` |

## Planning slice challenged

Adversarial review of `installer-validation-plan.md`: whether the branch matrix and `ReleaseEvidence` artifact can prevent false confidence, or whether it creates an evidence-shaped checklist that still hides destructive update, public-mode, funding, Electron, and adapter risks.

## Current-state facts

- Public README still advertises `npx create-workframe@0.1.6`, while the living audit records package metadata at `0.1.7`.
- Repository rules require evidence before inference, read-before-write mutation discipline, and source artifacts over memory.
- START_HERE says package sign-off is `Pack -> wipe sandbox -> create-workframe -> wizard -> chat`; dogfood green alone is not sign-off.
- The validation plan correctly separates package install, working cell, and deployment posture; it also keeps non-Hermes adapters inert for the next small release.
- The validation plan introduces eight branches: clean local, local with host runtimes, Docker plus provider credential, missing prerequisites, VPS/public, multi-user funding, existing generated install, and Electron shell.
- The prior red-team pass warned that a release gate skipped by the verifier is not a gate and that public launch readiness must be freshly verified, not persisted.

## Red-team contradictions / weak assumptions

### 1. The matrix is too broad to be the next release gate

The eight-branch matrix is useful as a map, but too large to be the first enforceable release gate. If every branch is treated as required for the next package release, the team will either stall or mark branches as manually waived. If only some branches are required, the artifact must say which ones are release-blocking.

Simpler rule:

```text
Release A required:
  A. clean Docker/Hermes local install
  C. Docker + BYOK provider path through current Hermes runtime
  G. existing generated install hard-stop / no-wipe proof

Release A explicitly non-blocking but documented:
  B. host runtime detection beyond marker-only
  D. guided install with no Docker
  E. public VPS readiness
  F. full multi-user funding correctness
  H. Electron shell
```

### 2. `ReleaseEvidence` can become a form without provenance

A markdown evidence file is only useful if it records the exact package artifact and the command surface used. Otherwise a future operator can accidentally validate monorepo source while claiming `npx` package readiness.

Minimum provenance must include:

```text
source_commit
package_artifact_kind: npm_pack | npm_dist_tag | local_registry | published_npx
package_artifact_identity: tarball hash or dist tag resolution
install_command_exact
fresh_target_path
host_os_context
validation_operator
validation_timestamp
```

Without this, `ReleaseEvidence` will look rigorous while failing reproducibility.

### 3. Existing-install safety is underweighted

Branch G is more important than it looks. `create-workframe MyBusiness` will be rerun by real users in existing folders. A clean install can pass while the dangerous path still wipes or corrupts `Agents/`, `Files/`, `.env`, vault data, or manifest state.

Release A should require a negative test: existing target with sentinel files must refuse destructive scaffold unless an explicit wipe verb is supplied. This is more important than Electron or non-Hermes discovery.

### 4. Provider credential path can falsely imply runtime readiness

Branch C says a Docker user with a provider credential should complete BYOK and chat through Hermes. Good. The hidden risk is copy/UI language: `OpenAI/Codex credential present` must not imply `Codex runtime available`. The validation artifact must distinguish provider success from runtime adapter success.

Required terms:

```text
provider_ready != runtime_ready
model_available != agent_can_execute
credential_saved != run_authorized
```

### 5. Public mode should not ride on the package release gate

Branch E is security-sensitive and environment-specific. If it is included in every release candidate, it will become stale or skipped. If it is omitted, public claims can overrun evidence.

Simpler split:

- package release gate proves local Docker/Hermes package truth;
- public launch gate is a separate live deploy checklist with timestamped environment evidence;
- docs must not market public VPS readiness unless the public gate was executed for that release or deployment.

### 6. Electron is a UI shell, not an installer proof

Branch H is valuable for the product path but dangerous as release evidence. A desktop shell can hide whether it is creating a cell, opening one, or connecting to a VPS. Until cell ownership and detection authority are settled, Electron should not be a release blocker or a proof of install safety.

First-principles rule: Electron may be a convenience shell only after the CLI/package cell contract is trustworthy.

### 7. Funding mode persistence is not enough for team safety

Branch F validates funding mode before invites. That is necessary but insufficient. Team safety depends on per-run payer resolution and `user_only` no-fallback behavior. A wizard-level setting can be true while delegated/scheduled runs still execute under the wrong payer.

Release copy should say:

```text
Team setup records intended funding mode.
Billing-grade per-run attribution is not yet claimed until RunFundingDecision + RunReceipt exist.
```

## Hidden complexity inventory

| Validation claim | Hidden failure mode | Safer evidence |
|---|---|---|
| Clean install works | Validated from monorepo, not packed artifact | Exact package artifact hash/dist tag plus clean target transcript |
| UI bundle works | Local dev build leaked into generated install | Generated install serves bundled UI after target wipe |
| Existing install safe | Clean install passes but rerun overwrites data | Sentinel-filled existing target refuses destructive scaffold |
| Provider ready | Credential saved but runtime cannot execute | Provider path and runtime path reported separately |
| Public-ready | Loopback health mistaken for public safety | Separate live public gate with HTTPS/SMTP/secrets/RBAC/env/network checks |
| Team funding ready | Wizard copy exists but run payer unresolved | Persisted setup decision now; per-run funding evidence deferred |
| Electron path ready | Desktop hides cell ownership | Electron excluded until cell-open/create/connect semantics are explicit |

## Simpler first-principles alternative

Do not make the next gate a broad product matrix. Make it a narrow, hard-to-fake package truth gate.

```text
PackageTruthGate v1
  1. Resolve package artifact
  2. Install into fresh target
  3. Boot Docker/Hermes cell
  4. Complete setup wizard with BYOK/provider path
  5. Stream first chat
  6. Verify generated UI bundle is served from target
  7. Rerun installer against existing target with sentinel files and prove no destructive overwrite
  8. Record ReleaseEvidence with artifact identity, commands, timestamps, and observed outputs
```

Everything else becomes named follow-on evidence:

```text
PublicLaunchGate
TeamFundingGate
PreflightRedactionGate
ElectronShellGate
SecondAdapterGate
```

This preserves the product direction without making the first release gate untestable.

## Security issues to pin before implementation

1. Do not let `ReleaseEvidence` omit the exact package artifact identity.
2. Do not let provider credentials imply Codex/Claude/Cursor runtime support.
3. Do not treat existing-install reopen/update as optional; destructive rerun risk is release-critical.
4. Do not persist `public_ready`; store only timestamped public verification evidence.
5. Do not include Electron in package truth until cell ownership semantics are explicit.
6. Do not claim billing-grade company-pays/hybrid correctness without per-run payer resolution and receipts.
7. Do not expand the matrix into a checklist that agents can satisfy with prose waivers.

## Proposed migration / refactor steps

1. Rename the next enforceable gate to `PackageTruthGate` in planning language.
2. Make branch A, branch C, and a destructive-rerun subset of branch G mandatory for the next small package release.
3. Move public VPS, Electron, full team funding, and non-Hermes adapter branches into separate named gates.
4. Require `ReleaseEvidence` to include source commit, exact package artifact identity, exact install command, target path, host context, timestamps, and observed outputs.
5. Add a sentinel-file no-overwrite scenario before any public installer promotion.
6. Keep `provider_ready`, `runtime_ready`, and `run_authorized` as separate evidence fields.
7. Treat branch D as a future guided-prerequisite UX gate, not as a package-release requirement.

## Next best red-team target

Deployment order and mode-selection state machine: challenge whether local, Docker, VPS, Electron, and reopen/update flows can be reduced to one safe sequence without mixing health, install completion, launch readiness, and runtime execution.
