# Release-readiness blockers

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
| Product surfaces | `docs/public/using-workframe.md` | `20ee82af97dc8aee9967eea768172d253471eca9` |
| VPS checklist | `infra/compose/workframe/PUBLIC_DEPLOY.md` | `2a6ec3188a5e75023b2a11aeaed778e06c12d6da` |
| Installer | `packages/create-workframe/bin/create-workframe.js` | `3983e3e5e9110f406ab0f7a5d238a34c00c066f0` |
| Installer identity helper | `packages/create-workframe/scripts/lib/install-identity.mjs` | `e2ceb2356b6112bbfec90520b0c60cd7212e825b` |
| Prior decision tree | `docs/living-audit/README.md` | `bcae35adef77b46c6774c9efbd075c2e0229b0ca` |
| Prior detection pass | `docs/living-audit/runtime-detection-map.md` | `b18f34648656426d455e53f9db9ee391c55b9322` |
| Prior config pass | `docs/living-audit/agent-runtime-config.md` | `9c6aa041be1c83d84165b54803db38ee32e48858` |
| Prior refactor pass | `docs/living-audit/refactor-map.md` | `5f8b28d129fa32320072371b8f260e2cfed87385` |
| Operator log | `operations/log.md` | `3bbbc1384f6ca400830ea4b043943cf3b64c9205` |

## Planning slice

Release-readiness blockers: convert living-audit convergence maps into strict release gates, separating blockers for the current Hermes/Docker package path from adapter-first deferrals that should not block the next small release.

## Current-state facts

- Public README and install docs still advertise `npx create-workframe@0.1.6`, while monorepo and installer package metadata are `0.1.7`.
- Public architecture still defines Workframe as a multi-user shell around Hermes.
- The generated install path is Docker/Hermes-first: `Agents/`, `Files/`, copied API/UI/supervisor, compose, and `workframe-manifest.json`.
- The current setup wizard already contains owner/admin, deployment mode, public URL, SMTP/admin, integrations, model billing, business profile, user profile, model keys, native agent, invites, and launch steps.
- Public mode already has a concrete fail-closed checklist: HTTPS `APP_BASE_URL`, SMTP, generated secrets, secure mode, supervisor token, proxy token, vault KEK, and no Docker socket on API.
- The harness scenario ledger has seven passing scenarios and two non-passing release gates: `installer-ui-bundle` and `dogfood-install-gate`.
- The harness runner skips manual and `cursor-local` scenarios, so cloud-green does not equal package release readiness.
- Current installer helper auto-resolves `native` deploy mode when host Hermes is detected; living-audit red-team notes argue this should not become silent adoption.

## Target-state mapping

The next release should be judged against two separate targets:

1. **Release target A — honest current product**
   - Ship a credible Docker/Hermes Workframe cell.
   - Keep Hermes as the only executable runtime.
   - Make version, install docs, setup wizard, public deploy gates, and install-gate evidence consistent.
   - Do not promise adapter-first runtime execution yet.

2. **Release target B — future adapter-first product**
   - Start introducing vocabulary for cell, preflight, runtime candidates, provider policy, funding policy, and receipts.
   - Keep non-Hermes CLIs inert until adapter harnesses exist.
   - Do not block Release target A on Codex/Claude/Cursor/OpenCode/OpenClaw/Copilot adapter support.

## Release blockers for the next small package release

| Blocker | Evidence | Required resolution |
|---|---|---|
| Version drift | README/install docs say `0.1.6`; packages say `0.1.7`. | Align public install command with the actually intended package version before publishing or tagging. |
| UI bundle parity not green | Harness marks `installer-ui-bundle` false and local-only. | Package release must include a verified bundled UI or an explicit no-release decision. |
| Full install-gate not green | Harness marks `dogfood-install-gate` false and manual. | Wipe/install/wizard/chat smoke must pass from the packed package, not only from monorepo dogfood. |
| Cloud CI is incomplete as release sign-off | `verify.mjs` skips manual and local-only gates. | Release checklist must explicitly require the skipped local gates. |
| Public identity overpromises if adapter-first language leaks early | Current architecture is Hermes shell; living audit is adapter-first planning. | Public docs must distinguish current executable runtime from future optional adapters. |
| Existing-runtime adoption is not safe enough for release claims | Current host Hermes detection can drive native/docker mode; no broader runtime preflight harness exists. | Do not market non-destructive adoption until preflight report and redaction tests exist. |
| Public/VPS gate must stay fail-closed | PUBLIC_DEPLOY requires HTTPS, SMTP, secrets, supervisor/proxy/vault posture. | Public deploy docs and wizard must not allow loopback health to imply public readiness. |
| Funding mode must be explicit before inviting teams | Existing docs describe BYOK/company-pays, but living audit requires run/payer attribution. | At minimum, team/public setup must show and persist BYOK/company/hybrid decision before invites. |

## Adapter-first deferrals that should not block the next release

- Executable Codex CLI, Claude CLI, Cursor, Copilot, OpenCode/OpenClaw, or custom runtime adapters.
- Full adapter registry implementation.
- Full run receipt ledger suitable for billing.
- Electron-owned local detection.
- Automatic provider/CLI auth detection.
- Host Hermes deep import, mount, copy, or session adoption.
- Multi-runtime model picker defaults.

These are important product direction items, but shipping them before the current package path is green would increase brittleness.

## Gaps / risks

- `doctor` appears in install docs as optional preflight, but the living-audit target preflight is stricter: mutation-free, redacted, and separate from install mutation. Naming can confuse users unless scope is clarified.
- Current public docs are honest about Hermes, but the strategy direction wants Workframe identity above Hermes. That transition needs careful copy: `Hermes is the default runtime today`, not `Workframe is Hermes` and not `Workframe already supports every runtime`.
- Release gating currently depends on local-only/manual evidence. Without a compact signed-off release artifact, future agents may over-trust cloud-green scenarios.
- Public multi-user mode allows full Hermes toolsets on shared workspace with isolation by profile/vault/supervisor. That can be defensible only if install-gate and public deploy verification remain mandatory.
- Version drift can cause users to install the wrong package while repository state and docs discuss another.

## Proposed migration / refactor steps

1. Treat the next release as a Hermes/Docker stabilization release, not an adapter release.
2. Fix documentation/package version alignment before any publish.
3. Make `installer-ui-bundle` and `dogfood-install-gate` mandatory release checklist items outside the cloud-only harness path.
4. Add or document a release sign-off artifact that records: package version, commit SHA, packed tarball identity, scaffold result, wizard completion, first chat smoke, public deploy posture if applicable.
5. Keep adapter-first planning under `docs/living-audit/` until a schema and harness exist.
6. Reframe existing runtime discovery as a future `preflight_report`, not as current adoption support.
7. Before team/public promotion, require visible funding policy persistence and fail-closed `user_only` semantics.
8. After release stabilization, implement the smallest non-behavioral seam first: `AgentIdentity` / `RuntimeBinding(kind=hermes)` naming around the existing Hermes path.

## Validation gates for this slice

| Gate | Evidence required |
|---|---|
| Version truth | README, docs, package metadata, and npm publish target agree. |
| Package truth | Packed `create-workframe` can scaffold, boot, complete wizard, and stream first chat. |
| UI truth | Generated install serves bundled UI without requiring monorepo build artifacts. |
| Public truth | Public mode refuses unsafe HTTP/missing secrets and passes `verify-public-deploy.sh`. |
| Funding truth | Team/public wizard persists BYOK/company/hybrid before invite flow. |
| Adapter truth | Public copy says non-Hermes adapters are planned/inert unless executable harness exists. |
| Safety truth | Existing host runtimes are not overwritten, mounted, copied, or silently adopted. |

## Open questions for later passes

- Should the next release be named `0.1.7` if docs already drifted to that package metadata, or should the next publish become `0.1.8` after fixing gates?
- Should `doctor` become the future preflight engine, or should `preflight --json` be a stricter separate command?
- What exact artifact should prove manual dogfood install-gate completion: harness JSON, release markdown, CI artifact, or signed commit note?
- Should public docs mention future adapters now, or keep them private until a second adapter has a harness?

## Next best planning target

Test/validation plan for installer journeys: convert these release blockers into a branch-by-branch verification matrix for local existing runtime, Docker no-runtime, clean install, VPS/public, team funding, and existing install reopen.
