# PackageTruthGate — v0.1.x release decision memo

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
| Public install doc | `docs/public/install.md` | `0ece45f99eb63781e090faefa670a61d3f33d265` |
| Public architecture doc | `docs/public/architecture.md` | `df9acf46cad326df2a6e211dfd48608794ee42b4` |
| Public security doc | `docs/public/security.md` | `3ab7a2408a92be7e8b6115bd798684b342cd5424` |
| Public release doc | `docs/public/release.md` | `85de1e4ed33b1e12b848232abdf5a5f99820840a` |
| Latest synthesis | `docs/living-audit/final-convergence-synthesis.md` | `23c373f0cb5d776337e4a9a33e0ce47d3a844a2f` |
| Latest red team | `docs/living-audit/red-team-11-gate-theater-risk.md` | `3b291251695a4907b6c545e21dbb7d70dc418da5` |
| Operator log | `operations/log.md` | `dc108cb871b176bc535d708d3f9081e1271a5bfb` |

## Planning slice

Define the v0.1.x `PackageTruthGate`: the smallest release-blocking decision system that proves the published `create-workframe` package can create a clean Workframe cell and run one managed-Hermes chat without relying on source-repo dogfood optimism.

## Current-state facts

- Public README and install docs still show `npx create-workframe@0.1.6`, while monorepo and installer package metadata are `0.1.7`. This is a release trust drift, not an architecture question.
- The repo describes Workframe as a multi-user shell around Hermes, with UI, API, installer, supervisor, and Docker Compose as current product surfaces.
- Generated installs receive copied API, UI, and supervisor artifacts from the npm package, so source build success is insufficient unless package contents are proven.
- The current harness has cloud-owned green checks for API/build/scaffold, but `installer-ui-bundle` and `dogfood-install-gate` remain local/manual false scenarios.
- Release docs already describe an install gate before publish, but the evidence artifact, owner, denial semantics, and negative cases are not yet canonical.
- Security docs require `SECURE_MODE=true` posture, supervisor ownership of the Docker socket, vault/lease boundaries, HTTPS/SMTP/secrets for public mode, and no public unsafe flags.
- Living-audit synthesis and red-team passes converge on one point: more named gates are useless unless a gate can block and emit comparable evidence.

## Target-state mapping

`PackageTruthGate` should answer one release question:

```text
Can a clean user install the exact package version being published, complete first-run setup, and execute one first chat through managed Hermes Docker without hidden source-repo assumptions or unsafe authority bypasses?
```

For v0.1.x, the gate should scope in:

```text
source/package version agreement
npm package contents and bundled UI parity
clean target creation only
Docker compose boot
setup wizard completion for single_user_local
API/supervisor/Hermes health
first managed-Hermes chat
redacted release evidence artifact
negative tests for unsafe install paths
```

It should scope out:

```text
Electron-native installation
public VPS production launch
team invites beyond documented policy
company-pays/hybrid execution
host Hermes execution
Codex/Claude/Cursor/Copilot/OpenCode execution
open/update/connect/adopt mutations
billing-grade receipts
```

## Gate contract

```text
PackageTruthGate
  owner_component: release harness / installer package, not UI alone
  allowed_inputs: git_ref, package_version, packed tarball path, clean target dir, loopback Docker environment
  forbidden_inputs: source-tree hotfixes inside generated install, host Hermes auth/config imports, public unsafe flags, non-empty target overwrite
  decision_values: allow | deny | needs_user_action
  evidence_path: operations/release-evidence/<package_version>/<scenario_id>.json (future durable path)
  user_visible_state: release candidate green | blocked with reason | local-only evidence missing
  blocks: npm publish/sign-off claim, README install bump, public install marketing
  negative_tests: non-empty target, missing Docker, missing LLM key, detected host runtime, forbidden workspace fallback
  deferrals: public VPS, Electron setup, second runtime adapter, team funding execution
```

## Minimal evidence schema

```json
{
  "schema_version": "0.1",
  "gate_name": "PackageTruthGate",
  "scenario_id": "clean-single-user-managed-hermes-first-chat",
  "git_ref": "<commit sha or tag>",
  "package_name": "create-workframe",
  "package_version": "0.1.x",
  "packed_artifact": "<redacted path or digest>",
  "target_mode": "single_user_local",
  "decision": "allow|deny|needs_user_action",
  "decision_reason": "<short reason>",
  "commands_executed": ["<redacted command list>"],
  "observed_outputs_redacted": {
    "ui_loaded": true,
    "api_health_ok": true,
    "supervisor_health_ok": true,
    "managed_hermes_health_ok": true,
    "wizard_completed": true,
    "first_chat_ok": true
  },
  "negative_cases": [
    { "id": "non_empty_target", "decision": "deny" },
    { "id": "missing_docker", "decision": "needs_user_action" },
    { "id": "host_runtime_detected", "decision": "detected_only" }
  ],
  "artifact_paths": [],
  "timestamp": "<iso8601>"
}
```

## Current gaps / risks

| Gap | Risk | Simpler posture |
|---|---|---|
| README/install version drift | User installs old version while package metadata says new version | Version agreement is a release blocker. |
| Cloud harness skips local-only gates | Green CI can mask broken package install | Publish requires local package evidence or explicit blocked state. |
| Install docs include optional doctor but no authority distinction | Doctor output can be mistaken for permission to mutate | Doctor is advisory only; gate decides. |
| Generated install copies product artifacts | Source tests can pass while packed app is stale | Evidence must run from the packed artifact. |
| Full wizard includes team/public branches | v0.1.x proof matrix explodes | First gate proves single-user local only; other modes become checklist/blocked. |
| Public/security posture spans many secrets | Public launch can be claimed before HTTPS/SMTP/vault proof | Public mode remains outside PackageTruthGate except as deferred risk. |
| Host runtime detection/adoption pressure | Installer could read or overwrite existing auth/config | Host runtimes are detected-only and redacted. |

## Proposed migration / refactor steps

1. Treat `PackageTruthGate` as the only v0.1.x release-blocking planning artifact.
2. Add a future durable evidence folder or schema before producing more release screenshots or ad-hoc markdown proof.
3. Make release-facing version agreement explicit: README, install docs, package metadata, tag, and npm version must match.
4. Define the clean install scenario from packed package only: pack, create clean target, boot Docker, complete single-user wizard, connect/verify key path, first chat.
5. Define negative scenarios before broadening happy paths: non-empty target deny, missing Docker guided block, host runtime detected-only, missing BYOK key no chat, `user_only` no workspace fallback.
6. Keep non-Hermes runtimes out of selectable agent profile execution until adapter harnesses exist.
7. Keep Electron/VPS/team/company-pays/hybrid as documented future branches until the single-user package path is repeatable.
8. Convert the gate into implementation tickets only after this planning rail finishes; no product source changes in this pass.

## Open questions for implementation tickets

- Where should release evidence live permanently: `operations/release-evidence/`, `.harness/evidence/`, or CI artifacts only?
- Should `install-gate.sh` produce machine-readable JSON directly, or should a wrapper collect evidence from existing scripts?
- What is the exact minimum first-chat assertion: HTTP 200, streamed token, persisted session, activity receipt, or all four?
- Which component owns the non-empty-target denial: installer CLI, lifecycle CLI, or shared package utility?
- Should README version drift be fixed only during release bump PRs, or continuously enforced by a verify script?

## Next best planning target

Create the final planning-rail handoff: a compact implementation-ticket backlog ranked by release blocker severity, using the convergence docs plus red-team diagnostics as inputs.
