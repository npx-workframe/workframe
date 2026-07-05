# Environment and runtime detection map

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
| VPS checklist | `infra/compose/workframe/PUBLIC_DEPLOY.md` | `2a6ec3188a5e75023b2a11aeaed778e06c12d6da` |
| Installer | `packages/create-workframe/bin/create-workframe.js` | `3983e3e5e9110f406ab0f7a5d238a34c00c066f0` |
| Installer identity helper | `packages/create-workframe/scripts/lib/install-identity.mjs` | `e2ceb2356b6112bbfec90520b0c60cd7212e825b` |
| API | `services/workframe-api/server.py` | `52e962760c28ad0eb70240287ed49aa746d3767b` |
| Install API | `services/workframe-api/install_api.py` | `b204c25a0916083e20947ae395c3f827e08a3d44` |
| Supervisor | `services/workframe-supervisor/server.py` | `2ffcbfd84da421f59b62bb371f08fc727b560f70` |
| Prior planning | `docs/living-audit/README.md` | `bcae35adef77b46c6774c9efbd075c2e0229b0ca` |
| Prior wizard pass | `docs/living-audit/first-run-wizard.md` | `b95a44a1709efdd6b2fdf05701c79b852b09477e` |
| Prior red-team pass | `docs/living-audit/red-team-01-adoption-risk.md` | `cf5ab6a80f2341fdeafb6aac6d1ada158493e057` |

## Planning slice

Environment/runtime detection map: safe discovery, forbidden discovery, target report shape, and validation gates for a future mutation-free preflight step.

## Current-state facts

- README and install docs advertise `create-workframe@0.1.6`; monorepo and installer package metadata are `0.1.7`.
- Current public docs define Workframe as a multi-user shell around Hermes.
- Current installer package description is explicitly `Workframe + Hermes`; generated installs create `Agents/` and `Files/` and launch the Docker/Hermes path.
- Current helper code already has a narrow detection seam: it checks for a Hermes home marker and can choose `native` versus `docker` deploy mode.
- Current install readiness is still Hermes-centered: phase is derived from Hermes presence plus setup completeness.
- Current security primitives are useful for the target path: secure default, supervisor boundary, vault, per-turn leases, invite-only public mode, and `user_only` provider behavior.
- Current harness does not validate read-only runtime detection, redacted detection output, existing-install reopen, non-destructive target handling, or adapter candidate classification.

## Detection principles

1. Detection is not adoption.
2. Detection must be read-only and side-effect-free.
3. Detection reports capability posture, not private contents.
4. Detection output is redacted by default.
5. A detected CLI or runtime is only an inert candidate until an adapter has a validation harness.
6. Existing Workframe installs are reopened or repaired, not overwritten.
7. Host runtime homes are never mounted, copied, or modified by default.
8. Public launch readiness is separate from local health, install completion, and runtime presence.

## Target preflight report

The future preflight command should return a compact report with these sections:

| Section | Purpose |
|---|---|
| `host` | OS, architecture, shell family, local browser posture. |
| `cell` | Target path status, manifest status, install completion, port availability. |
| `substrates` | Node, Docker, Compose, browser, public host posture. |
| `runtime_candidates` | Hermes, Claude CLI, Codex/OpenAI CLI, Cursor, OpenCode/OpenClaw, Copilot, or custom candidates. |
| `provider_posture` | Provider/funding posture as present, absent, or unknown; no private value exposure. |
| `recommended_plan` | `reopen_existing`, `new_docker_hermes_default`, `repair_existing`, `blocked_missing_substrate`, or `public_vps_needs_prereqs`. |
| `risk_notes` | Redacted warnings and required consent boundaries. |

The report must not create folders, pull images, start containers, open browsers, write manifests, modify discovered runtime homes, repair configs, or authenticate third-party tools.

## Safe probe map

| Target | Allowed probe | Output | Forbidden probe |
|---|---|---|---|
| Existing Workframe cell | Check target path, manifest presence, expected folders, known compose filenames. | existing / partial / missing / non-Workframe. | Reading private config values or overwriting target. |
| Node | Version command from current PATH. | supported / missing / unsupported. | Installing or changing PATH. |
| Docker | Version and daemon availability checks. | client / compose / daemon posture. | Pulling images, creating containers, or changing daemon state. |
| Ports | Local connection test on Workframe slot ports. | available / occupied / partial. | Killing processes or rebinding ports. |
| Host Hermes | Marker-only presence check with redacted path label. | host Hermes candidate. | Reading profiles, copying sessions, or mounting host home. |
| Managed Hermes | Check generated cell profile markers inside the Workframe target only. | managed profile readiness. | Treating host Hermes as managed Workframe state. |
| Agentic CLIs | Non-auth version/help probes only when executable is present. | inert runtime candidate. | Login flows, private cache reads, workspace history reads, or mutation. |
| Provider posture | Workframe-owned vault/config records after user setup, or explicit user-declared posture. | present / absent / unknown. | Printing, validating, or copying private credential material. |
| VPS/public | HTTPS/public URL posture, SMTP tested status, required secret presence as booleans, invite policy, backup posture. | public launch gate inputs. | Treating loopback health as public readiness. |

## Candidate classification model

```text
DetectedRuntimeCandidate
  kind: hermes | claude_cli | codex_cli | cursor | opencode | openclaw | copilot | unknown
  source: path | env | cell_manifest | docker | user_declared
  scope: host | workframe_cell | docker_image | remote
  auth_posture: ready | missing | unknown | unsupported
  workspace_boundary: workframe_files | external_project | unknown | none
  executable: false by default

ValidatedRuntimeAdapter
  DetectedRuntimeCandidate plus:
  can_start, can_stream, can_cancel, can_capture_logs, can_write_receipt
  credential_boundary: vault_lease | cli_session | workspace_policy | none
  harness_scenario: required before executable=true
```

## Target-state mapping

- `npx create-workframe MyBusiness` should begin with preflight. If `MyBusiness/` exists, recommend reopen, repair, or block; do not silently overwrite.
- A clean machine should recommend `new_docker_hermes_default`, because Hermes Docker is the current validated runtime path.
- A machine with Claude, Codex, Cursor, OpenCode/OpenClaw, or Copilot should list those tools as inert candidates until an adapter contract and harness exist.
- A machine with provider posture but no runtime should not be treated as runtime-ready.
- Public/VPS setup needs a dedicated launch gate: HTTPS, SMTP tested, generated required secrets present, invite policy, admin identity, backup posture, API without Docker socket, and gateway without sensitive environment.
- Agent profiles should eventually bind agent role, runtime adapter, provider policy, and funding policy independently, but only after detection and adapter classification exist.

## Gaps / risks

- Existing Hermes detection is useful but currently too close to deploy-mode selection; host Hermes presence should not automatically imply native deploy.
- Detection output can leak privacy through paths, profile names, container names, project names, CLI status, or provider names; redaction must come before implementation.
- Windows, WSL, Docker Desktop, macOS app bundles, Linux VPS, and browser/Electron shells can disagree about the real runtime environment.
- Safe auth posture detection for third-party CLIs may be impossible without user consent; default should be `unknown`, not speculative confidence.
- Current install status vocabulary is too Hermes-centric for adapter-first cells.
- Adding probes directly to the monolithic installer would make it brittle; preflight should be a separate module and report.

## Proposed migration / refactor steps

1. Define the detection report schema and redaction policy before writing implementation code.
2. Convert current Hermes detection into an inert candidate report, not an automatic deploy-mode decision.
3. Split install planning into `preflight_report -> install_plan -> explicit_confirm -> mutation -> validation`.
4. Add a target-path gate before scaffold generation; existing paths must stop unless the user selects repair, upgrade, or wipe.
5. Keep `hermes_docker_default` as the only executable adapter until another adapter has full validation.
6. Add fixture-based tests using fake homes, fake PATH entries, and fake target directories.
7. Add public launch validation as its own gate, separate from local health and install completion.
8. Expose the detection report in first-run wizard and Electron only after the report is redacted and tested.

## Validation gates for this slice

| Gate | Evidence required |
|---|---|
| No mutation | Fixture preflight leaves fake home, target, and PATH fixtures unchanged. |
| Redaction | Report excludes private paths, private config contents, account labels, and secret-like values by default. |
| Existing path hard-stop | Existing target directory never routes to scaffold overwrite without explicit destructive verb. |
| Host Hermes safe | Host Hermes candidate reports marker-only presence unless user opts into a deeper local probe. |
| Provider safe | Provider posture never exposes private credential material. |
| Candidate inertness | Non-Hermes CLIs are not executable until a harness-backed adapter marks them valid. |
| VPS fail-closed | Public mode cannot be launch-ready from loopback health alone. |

## Open questions for later passes

- Which second adapter is easiest to validate end-to-end after Hermes: Codex CLI, Claude CLI, Cursor, or OpenCode/OpenClaw?
- Should Electron run preflight locally and pass a report to the web UI, or should the generated cell API own all detection?
- How much provider posture can be checked without violating privacy: presence only, auth status, or user-confirmed account label?
- Should detection reports be stored in the manifest, API DB, Workframe runtime folder, or shown transiently until the user confirms a plan?

## Next best planning target

Agent profile/provider/runtime config model: define the minimal schema that lets architect/coder/docs agents differ by runtime, provider, model, and funding policy without implementing non-Hermes execution yet.
