# Red team 02 — detection privacy, false confidence, and launch-gate drift

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
| Architecture docs | `docs/public/architecture.md` | `df9acf46cad326df2a6e211dfd48608794ee42b4` |
| Security docs | `docs/public/security.md` | `3ab7a2408a92be7e8b6115bd798684b342cd5424` |
| Installer | `packages/create-workframe/bin/create-workframe.js` | `3983e3e5e9110f406ab0f7a5d238a34c00c066f0` |
| Installer identity helper | `packages/create-workframe/scripts/lib/install-identity.mjs` | `e2ceb2356b6112bbfec90520b0c60cd7212e825b` |
| Living audit base | `docs/living-audit/README.md` | `bcae35adef77b46c6774c9efbd075c2e0229b0ca` |
| First-run pass | `docs/living-audit/first-run-wizard.md` | `b95a44a1709efdd6b2fdf05701c79b852b09477e` |
| Runtime detection pass | `docs/living-audit/runtime-detection-map.md` | `b18f34648656426d455e53f9db9ee391c55b9322` |
| Prior red team | `docs/living-audit/red-team-01-adoption-risk.md` | `cf5ab6a80f2341fdeafb6aac6d1ada158493e057` |
| Operator log | `operations/log.md` | `4c7bae839312a1b600b6a896cdaef5b58b79f3f3` |

## Planning slice challenged

Adversarial review of `runtime-detection-map.md`, focused on privacy leakage, false readiness, cross-platform ambiguity, and gaps between cell-local safety and public/multi-user safety.

## Current-state facts

- Current public identity still says Workframe is a multi-user shell around Hermes, while the planning rail is intentionally moving toward Workframe as an adapter-first cell.
- Current generated installs mount `Agents/` into `/opt/data` and `Files/` into `/workspace`; public docs say files are durable truth and agents/runtime state is shared Hermes profile state.
- Current security docs rely on `SECURE_MODE`, a supervisor boundary, vault encryption, per-turn leases, invite-only public mode, and `user_only` no-fallback provider behavior.
- Public mode explicitly requires HTTPS, vault KEK, SMTP, proxy token, supervisor token, invite-only auth, admin-only dashboard, member limits to `u-{user}-*` profiles, gateway allowlisted secrets, and supervisor blocks around direct `.env` / `auth.json` paths.
- Current installer helper can detect host Hermes by checking known config paths and returns a concrete path when found.
- `resolveDeployMode('auto')` chooses `native` when host Hermes is detected, so detection can already influence deploy mode rather than remaining inert.
- Current scaffold writes generated `.env`, Docker compose, scripts, `Agents/`, `Files/`, seed profiles, and generated docs after target preparation.
- Current harness skips local-only installer UI bundle parity and manual dogfood install-gate in cloud, so the riskiest installer journeys are not enforced by the automated cloud loop.

## Red-team contradictions / weak assumptions

### 1. “Read-only” is not automatically safe

The detection map correctly says probes must not mutate. That is insufficient. A read-only probe can still leak private project names, usernames, directory structure, account labels, container names, model/provider posture, or auth readiness into logs, manifests, telemetry, screenshots, support bundles, or chat.

Stronger rule: detection output must be private by construction. The default user-visible report should contain coarse categories only:

```text
host_hermes: maybe | present | absent
agentic_cli: present_count only until user expands
provider_posture: unknown unless Workframe-owned or user-declared
paths: never shown by default
account labels: never shown by default
```

### 2. Existing `detectHermesHome()` violates the future report boundary

The helper currently returns the actual Hermes home path. That may be acceptable for internal installer logic, but it is unsafe as a future user-visible or stored detection report. It also encourages `auto -> native` deploy selection.

First-principles alternative: split detection into two layers:

| Layer | Allowed output | Storage |
|---|---|---|
| `private_probe_result` | Raw paths and exact executable details inside process memory only. | Not persisted by default. |
| `redacted_preflight_report` | Booleans, coarse posture, risk notes, consent prompts. | May be shown/stored. |

Only a user action like “reveal path” or “bind this runtime” should expose or persist exact local paths.

### 3. Cross-environment detection can lie

A future Electron shell, Node installer, WSL terminal, Docker container, browser UI, and VPS SSH session may each see a different machine. A CLI detected in Windows PATH may be unusable from WSL. Docker Desktop may be available to the host but not to the current shell. A browser may be local while the API is remote. A VPS may pass loopback health while public DNS/HTTPS/SMTP fail.

The detection report needs a `probe_context` field before any recommendation:

```text
probe_context:
  runner: npx_node | electron_main | api_container | supervisor_container | vps_ssh | browser_only
  os_view: windows | wsl | macos | linux | container
  can_mutate_target: false
  can_see_host_home: true/false
  can_access_docker_daemon: true/false
  can_validate_public_url: true/false
```

Without this, the wizard will over-trust stale or context-local facts.

### 4. Provider posture is currently the most dangerous false-positive

The detection map says provider posture can be `present / absent / unknown`. For third-party CLIs and OAuth sessions, `present` is usually not safe to claim without touching private caches or triggering network/auth behavior.

Safer default:

```text
provider_posture:
  workframe_vault: present | absent
  user_declared: present | absent | skipped
  third_party_cli: unknown_by_default
```

The wizard may say “you can connect Codex/OpenAI/OpenRouter/Anthropic later,” not “found usable auth,” unless the evidence comes from Workframe-owned vault state or explicit user declaration.

### 5. Public launch readiness is not a detection item; it is a live validation gate

The planning pass includes public-host posture inside preflight. That is useful, but dangerous if treated as cached detection. HTTPS, SMTP deliverability, domain DNS, firewall, backup status, and invite policy can change after detection.

Public mode should have two separate states:

- `public_prereqs_detected`: static/cached evidence collected during setup.
- `public_launch_verified_at`: fresh validation timestamp from live checks before public exposure.

No cached preflight report should make `public_multi_user` launch-ready.

### 6. Adapter candidates can become product promises too early

Listing Codex, Claude CLI, Cursor, Copilot, OpenCode/OpenClaw, and Hermes in the first-run wizard creates implied support. If these remain inert candidates, the UI copy must be explicit: “Detected only. Not yet runnable through Workframe.”

Simpler alternative for the next product path: do not show non-Hermes runtime candidates in the primary wizard. Put them behind an “Experimental adapters / future integrations” panel until a second adapter is validated end-to-end.

## Security issues to pin before implementation

1. Do not persist raw detection paths by default.
2. Do not include exact CLI names/account labels/provider names in support bundles unless the user exports a diagnostics bundle explicitly.
3. Do not let `auto` deploy mode select host/native behavior solely from host Hermes presence.
4. Do not run CLI `auth status`, `whoami`, `doctor`, or provider validation commands during general preflight unless each command has been classified as non-mutating and privacy-safe.
5. Do not let API/container-side detection infer host-side availability.
6. Do not cache public launch readiness as install readiness.
7. Do not make “detected adapter candidate” look selectable as an execution runtime.

## Simpler first-principles alternative

```text
v0.1.x red-team recommendation:
  - keep Hermes Docker as the only executable runtime path
  - add target-path no-overwrite doctrine before adoption features
  - add redacted `doctor` output for current cell only
  - avoid broad host runtime discovery in primary setup

v0.2:
  - add probe_context + redacted_preflight_report schema
  - detect host tools only as hidden/expandable candidates
  - never persist raw paths without explicit consent
  - keep public_launch_verified separate from install_complete

v0.3:
  - validate exactly one second adapter end-to-end
  - expose that adapter as selectable only after run receipts, cancellation, logs, workspace boundary, auth boundary, and tests exist
```

## Proposed migration / refactor steps

1. Amend the planning doctrine: mutation-free detection must also be privacy-minimizing and context-labeled.
2. Define `probe_context`, `private_probe_result`, and `redacted_preflight_report` as separate concepts.
3. Make `DetectedRuntimeCandidate.executable = false` and `visible_in_primary_wizard = false` unless backed by a validated adapter harness.
4. Change future `auto` deploy planning so host Hermes presence never automatically chooses native adoption.
5. Add a future harness fixture that proves raw paths do not appear in generated reports, logs, manifests, or support exports by default.
6. Split `install_complete`, `first_chat_verified`, and `public_launch_verified_at`; public launch must use live validation, not cached detection.
7. Put non-Hermes candidate discovery behind an explicit diagnostics/experimental panel until the second adapter is real.

## Gaps / risks

- The planning rail is drifting toward a broad “detect everything” wizard, which increases privacy and support risk before it increases product value.
- The current helper shape (`detectHermesHome() -> raw path`, `resolveDeployMode(auto) -> native when found`) is the opposite of the inert, redacted detection model.
- Public mode requires stricter live validation than the current cell-local install status vocabulary.
- Cloud harness skips the exact installer/local gates that would catch many user-journey failures.

## Next best red-team target

Agent profile/provider/runtime config model: challenge whether role, runtime, provider, model, funding, credential scope, workspace boundary, and delegation billing can be represented without producing an untestable matrix before a second adapter exists.
