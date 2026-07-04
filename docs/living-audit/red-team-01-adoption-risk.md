# Red team 01 — adoption risk and installer category errors

Temporary living-audit planning material. Not public release doctrine. Planning only; no product source-code changes are implied by this file.

## Inspected ref / SHAs

Repository resolved directly: `npx-workframe/workframe`, default branch `main`.

| Area | Path | Blob SHA |
|---|---|---|
| Living audit base | `docs/living-audit/README.md` | `bcae35adef77b46c6774c9efbd075c2e0229b0ca` |
| Latest planning pass | `docs/living-audit/first-run-wizard.md` | `b95a44a1709efdd6b2fdf05701c79b852b09477e` |
| Red-team smoke test | `docs/living-audit/red-team-smoke-test-2026-07-04.md` | `e9acd36379978ef0ceffae955ddba37628f43d04` |
| Installer | `packages/create-workframe/bin/create-workframe.js` | `3983e3e5e9110f406ab0f7a5d238a34c00c066f0` |
| Install API | `services/workframe-api/install_api.py` | `b204c25a0916083e20947ae395c3f827e08a3d44` |
| Harness scenarios | `.harness/feature_list.json` | `ed32c988e668d813e99d8f332ebd2d22b3fbb95e` |
| Operator log | `operations/log.md` | `62158dc024d32d58549eeee0da3a34ce036840fa` |

## Planning slice challenged

Adversarial review of the first-run wizard and installer decision-tree assumptions, focused on non-destructive adoption of existing runtimes, provider credentials, and user setups.

## Current-state facts

- The planning rail correctly identifies the target path as `detect -> plan -> confirm -> mutate -> validate`, but the current CLI still collapses a positional project name into `yes`, `force`, install actions, and Docker pull by default.
- The current scaffold path deletes an existing target directory when `--force` is active. A normal `npx create-workframe MyBusiness` positional invocation sets `force = true`, so the common path is destructive unless guarded earlier by future logic.
- The generated stack is Hermes-profile-first: it creates `Agents/`, `Files/`, seed profiles, profile config, `bootstrap-native`, `bootstrap-profiles`, `add-profile`, `chat`, and `update-hermes` scripts around Hermes commands and the Docker image.
- Native deploy is not host runtime adoption. If `--deploy native` is selected, the installer requires existing Hermes config, but still writes an isolated generated `Agents/` runtime and only records host Hermes location in `NATIVE-HERMES.txt`.
- Install readiness is still Hermes-centered: `install_status_payload` derives phase from `hermes_present` and `setup_complete`, and `_setup_complete` can fall back to native Hermes presence when DB checks fail.
- Public readiness has some useful gates, but URL testing is still separate from the install phase model and does not yet become a single fail-closed launch gate.
- The harness currently verifies scaffold, build, provider surfaces, SMTP behavior, public repo hygiene, and manual dogfood install-gate. It does not cover no-overwrite adoption, runtime adapter detection, existing-install reopen, or adapter-profile binding.

## Red-team contradictions / category errors

### 1. Detection is being treated as adoption

The first-run plan says the wizard can find Hermes, Claude, Codex, Cursor, OpenCode/OpenClaw, Copilot, provider keys, and OAuth posture, then expose them as adapters. That skips a missing product layer: detected asset != usable adapter.

A usable adapter needs an execution contract, auth boundary, workspace mapping, streaming/log capture, run cancellation, audit receipt, failure taxonomy, and upgrade behavior. None of that exists in the current installer model. Detection should therefore produce only an inert report until an adapter has a validated runner.

### 2. `npx create-workframe MyBusiness` is currently unsafe as the canonical adoption entry

The target doctrine wants `npx create-workframe MyBusiness` to be the front door for both new installs and existing setups. The current parser turns a positional project name into non-interactive defaults, `--force`, Docker pull, and install launch. That is acceptable for a clean scaffold generator, but not for a non-destructive adoption wizard.

First-principles alternative: a positional project name may create a new cell only when the target path does not exist. If the path exists, the installer must stop in read-only inspect mode and require an explicit `repair`, `upgrade`, or `wipe` verb.

### 3. Host Hermes adoption is more dangerous than the planning rail implies

The current repo is intentionally avoiding host Hermes mounts. That is good. The planning rail should not weaken this too early. Host Hermes can contain personal identity, keys, sessions, memories, and tool configuration. Even read-only profile probing can leak private project names or model/provider posture into Workframe logs.

Safer alternative: host Hermes is an external tool candidate, not an adopted runtime, until Workframe has an explicit consent screen and a local-only probe that redacts path, identity, and secrets by default.

### 4. Provider auth is being conflated with runtime readiness

Having Codex/OpenAI/OpenRouter/Anthropic credentials does not mean Workframe can execute agent runs safely. It only means a funding/provider posture may exist. Runtime readiness requires a runner and workspace boundary. The target plan should split:

- `provider_posture`: user may be able to fund model calls.
- `runtime_posture`: an executable agent harness exists.
- `adapter_posture`: Workframe can broker that runtime with audit and cancellation.
- `profile_binding`: an agent profile has a chosen adapter and provider policy.

### 5. Multi-runtime profiles risk creating a matrix before one adapter is real

The target examples are useful: architect via GPT-5.5/Codex OAuth, coder via Kimi/OpenRouter through Hermes, docs via Cursor or Claude. But this creates a combinatorial support matrix before the product has one adapter seam.

Simpler path: support exactly one validated adapter contract first: `hermes_docker_default`. Model/profile differences should remain within that adapter until Workframe proves a second adapter end-to-end.

### 6. Public/VPS launch is still too easy to confuse with local health

The public install requirements are stronger than the current install status vocabulary. The wizard needs a separate `public_launch_ready` gate that cannot be satisfied by loopback health, Docker container health, or SMTP config alone. It must require public URL reachability, HTTPS, SMTP tested, invite policy, admin identity, backup path, generated secrets, and secure-mode posture.

## Hidden complexity inventory

| Assumption | Hidden complexity |
|---|---|
| Detect existing CLI | Cross-platform install paths, version commands, auth checks, noninteractive behavior, token redaction, PATH shims, WSL vs Windows split. |
| Adopt existing runtime | Workspace mount semantics, process ownership, cancellation, logs, rate limits, user identity, secrets boundary, upgrade breakage. |
| Adapter-first profiles | Schema migration, UI config, runtime health, run receipt format, provider/funding policy, per-user isolation. |
| Electron first-run | OS permissions, Docker Desktop detection/install, protocol handlers, local server lifecycle, updates, code signing. |
| VPS setup | DNS propagation, TLS, SMTP deliverability, reverse proxy, backups, firewall, admin recovery, secret rotation. |
| Existing Workframe reopen | Manifest compatibility, partial installs, failed bootstraps, stale Docker containers, port collisions, old package versions. |

## Security risks to pin before implementation

1. Do not read token files, config files, OAuth caches, or CLI home directories during detection unless the user explicitly selected a specific tool and consented to a named probe.
2. Do not log absolute paths to private runtime homes by default. Use redacted labels like `host_hermes_detected` plus user-confirmed reveal.
3. Do not mount host runtime homes into Docker by default, even read-only. A read-only mount can still expose private memory and credentials to a container boundary.
4. Do not allow company-pays fallback for `user_only` providers. Funding policy must be explicit before invitations and before delegated runs.
5. Do not equate `install_complete` with safe public operation. Public mode needs its own launch gate.
6. Do not put adapter health behind the same field as Hermes profile health. Cell, runtime, provider, funding, public-host, and first-chat gates must remain separable.

## Simpler first-principles alternative

For the next credible product path, avoid general multi-runtime adoption in the installer.

```text
v0.1.x: Hermes Docker cell remains the only executable default.
  - installer becomes non-destructive for existing target directories
  - add read-only `doctor` report for environment and current cell
  - public mode gets a strict launch gate
  - funding policy is persisted before invites

v0.2: adapter schema exists, but only Hermes adapter is executable.
  - external CLIs are listed as `detected_candidates`, not usable runtimes
  - no host runtime mounts
  - no provider secret reads

v0.3: one second adapter is implemented end-to-end.
  - choose the easiest verifiable adapter, not the most strategic one
  - add run receipt, cancellation, logs, workspace mapping, and tests

Only after v0.3: first-run wizard may bind non-Hermes runtimes.
```

## Proposed migration / refactor steps

1. Patch the planning doctrine: `DetectedRuntimeCandidate` must be inert by default; only `ValidatedRuntimeAdapter` can execute runs.
2. Make existing target directories a hard stop in future installer design. Replace implicit `--force` on positional names with `inspect_existing` unless an explicit destructive verb is provided.
3. Define a minimal cell gate model before runtime adapter work:
   - `cell_scaffolded`
   - `workspace_ready`
   - `runtime_default_ready`
   - `provider_policy_ready`
   - `funding_policy_ready`
   - `public_launch_ready`
   - `first_chat_verified`
4. Keep `hermes_docker_default` as the only executable adapter until a second adapter has a full validation harness.
5. Add a redaction policy for detection outputs before adding any probes.
6. Add harness scenarios for: existing directory no-overwrite, positional command no destructive overwrite, host Hermes detected but not mounted, provider credential presence not read, public launch fails closed, and `install_complete` not equal to `public_launch_ready`.

## Gaps / risks

- The living audit now has two parallel targets: broad adapter-first ambition and current Hermes-centered reliability. Without a versioned migration ladder, agents may start implementing broad adapter abstractions prematurely.
- The current installer can still erase a named project directory through the ordinary positional command path. This is the highest-priority release-readiness risk for any adoption-focused future.
- The target product identity needs to decouple from Hermes in copy, but the implementation should not decouple execution until the adapter contract exists.
- Electron should not own runtime adoption yet. It should first be a shell/launcher around a validated cell and doctor report.

## Next best red-team target

Environment/runtime detection map: define allowed probes, forbidden probes, redaction rules, false-positive handling, and consent boundaries before the planning rail turns detection into implementation work.
