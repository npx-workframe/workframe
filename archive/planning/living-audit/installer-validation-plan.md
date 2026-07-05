# Installer journey validation plan

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
| Product surfaces | `docs/public/using-workframe.md` | `20ee82af97dc8aee9967eea768172d253471eca9` |
| Security docs | `docs/public/security.md` | `3ab7a2408a92be7e8b6115bd798684b342cd5424` |
| Public deploy checklist | `infra/compose/workframe/PUBLIC_DEPLOY.md` | `2a6ec3188a5e75023b2a11aeaed778e06c12d6da` |
| Installer | `packages/create-workframe/bin/create-workframe.js` | `3983e3e5e9110f406ab0f7a5d238a34c00c066f0` |
| Prior release pass | `docs/living-audit/release-readiness.md` | `3581c625be86e5e1fd7208c687c75af99115ea6d` |
| Prior red-team pass | `docs/living-audit/red-team-05-release-gate-risk.md` | `da5b40e246e7a2732decd4b295c4fbf08e6a2ed9` |
| Operator log | `operations/log.md` | `09052576dbeadaf09a465c6342a9b54124fea0be` |

## Planning slice

Test / validation plan for installer journeys: convert release-readiness blockers and red-team release-gate concerns into branch-by-branch evidence gates for the simplest credible Workframe installation path.

## Current-state facts

- Public README and install docs still advertise `npx create-workframe@0.1.6`, while monorepo and installer package metadata are `0.1.7`.
- Install docs define the end-user path as scaffold, optional `doctor`, Docker boot, setup wizard, then launch.
- The generated layout includes `Agents/`, `Files/`, copied API/UI/supervisor, compose, and `workframe-manifest.json`.
- The first-boot wizard already describes deployment mode, public URL, SMTP/admin, integrations, model billing, business profile, user profile, model keys, native agent, invites, and launch.
- Product surface docs claim rooms, DMs, activity, files, browser panel, agents, chat, create agent, model picker, skills, slash commands, profile, connected accounts, invites, stack keys, Hermes dashboard, @mentions, and Kanban.
- Public security docs require secure-mode boundaries, BYOK default, `user_only` no workspace fallback, vault, per-turn leases, invite-only public mode, dashboard owner/admin gating, runtime RBAC, gateway env allowlisting, and supervisor path guards.
- Public VPS docs require HTTPS `APP_BASE_URL`, SMTP, generated secrets, secure mode, proxy token, supervisor token, vault KEK, no API Docker socket, public overlay, post-deploy verification, and manual dashboard/env/network checks.
- Harness scenarios have seven green cloud-owned checks and two false local/manual release gates: `installer-ui-bundle` and `dogfood-install-gate`.
- Harness runner skips manual and `cursor-local` scenarios; therefore cloud-green cannot prove package readiness.
- Installer source generates Docker compose, mounts local `Agents/` and `Files/`, runs Hermes gateway, dashboard, API, supervisor, and UI containers, and includes a public overlay path for `public_multi_user`.

## Target-state mapping

Validation should treat Workframe as one cell with three evidence levels:

```text
Level 1: package installs
  npx/local pack creates an isolated project without escaping target path.

Level 2: cell works
  Docker/Hermes stack boots, wizard completes, first agent chat streams, core surfaces render.

Level 3: deployment posture is safe for the chosen mode
  local, trusted team, or public VPS gates match the security model before users are invited.
```

The next small release should validate Hermes/Docker execution only. Existing-runtime discovery and non-Hermes adapters should remain inert planning targets until they have fixture-safe preflight and adapter harnesses.

## Validation matrix

| Branch | User state | Required evidence | Must not do |
|---|---|---|---|
| A. Clean local install | No Hermes, no known agent CLI, Docker available | `create-workframe` scaffolds clean target; `.env` generated; UI bundle served; wizard launches; one native Hermes profile starts; first chat smoke succeeds. | Do not require host Hermes, provider OAuth, public DNS, SMTP, or non-Hermes adapter. |
| B. Local user with host Hermes / CLIs | Existing Hermes, Claude/Codex/Cursor/OpenCode configs may exist | Detection/preflight reports presence as redacted candidates only; install still creates isolated Workframe `Agents/` and `Files/`; no host profile import. | Do not copy, mount, mutate, delete, or silently adopt host runtime homes or auth files. |
| C. Docker user with provider credential | Docker available; user can add OpenAI/Codex/OpenRouter/etc. credential | Wizard can complete enough setup to connect model key, persist BYOK policy, create native agent, and start chat through current Hermes path. | Do not claim external CLI runtime support merely because provider credentials exist. |
| D. Guided user with nothing installed | No Docker or missing prerequisites | Preflight gives missing-prereq report and clear next action; scaffold either stops safely or creates only inert project files. | Do not partially boot, write outside target, or ask for secrets before runtime prerequisites are satisfied. |
| E. VPS / public self-host | Domain, HTTPS, SMTP, generated secrets, backup/upgrade posture needed | Public gate proves HTTPS base URL, SMTP, secure mode, vault/proxy/supervisor secrets, API no Docker socket, dashboard gate, gateway env allowlist, network separation, and backup/rollback instructions. | Do not treat loopback health, first chat, or install completion as public readiness. |
| F. Multi-user team | Invite flow plus BYOK/company/hybrid funding choice | Funding mode persisted before invites; invite-only auth path works; user profile creates `u-{user}-*` runtime binding; `user_only` providers do not fall back to workspace creds. | Do not imply billing-grade attribution before run-level funding decisions and receipts exist. |
| G. Existing generated Workframe install | User reruns install/update in a folder with Workframe artifacts | Tool detects existing manifest and offers reopen/update/backup path; routine update path preserves data. | Do not wipe `Agents/`, `Files/`, API data, vault, `.env`, or manifest without explicit backup/confirmation. |
| H. Electron download path | Desktop shell points to local or remote cell | Electron can explain whether it is creating a new cell, opening an existing local cell, or connecting to a remote VPS cell. | Do not hide cell ownership behind desktop UI or write into host runtime homes without preflight. |

## Evidence artifact shape

Every release candidate should produce one `ReleaseEvidence` artifact before publish/tag:

```text
ReleaseEvidence
  source_commit
  package_version
  package_artifact_hash_or_npm_dist_tag
  validation_started_at
  validation_finished_at
  clean_target_path
  branch_results[]
    branch_id
    mode
    commands_or_manual_steps
    expected_result
    observed_result
    passed
    evidence_notes
  first_chat_profile
  public_launch_verified_at?       # only for public mode
  funding_policy_verified?         # team/public only
  known_deferrals[]                # adapters, billing receipts, host adoption
```

This artifact may start as markdown, but it must separate source commit, package artifact, target path, mode, and observed result. It must not be replaced by `.harness/feature_list.json`, because local/manual package gates are intentionally outside cloud-only verification.

## Proposed migration / refactor steps

1. Stabilize the current package gate first: version truth, packed package identity, UI bundle parity, clean scaffold, wizard, first chat.
2. Split validation into three named gates: `local_package_gate`, `team_install_gate`, and `public_launch_gate`.
3. Keep `.harness/verify.mjs` for cloud-owned checks, but make release docs require explicit evidence for skipped local/manual gates.
4. Add a future fixture-safe preflight gate before any existing-runtime adoption: no mutation, redacted output, no raw auth paths/secrets, no host runtime import.
5. Add an existing-install reopen/update/backup test before promoting routine updates as safe.
6. Add a minimal team funding persistence test before team invites; defer billing-grade receipts to a later `RunFundingDecision` pass.
7. Add public live verification after every deploy/upgrade, not a persisted `public_ready` boolean.
8. Only after the Hermes/Docker path is green, define one second-runtime adapter harness with start, stream, cancel, logs, workspace, funding, and audit evidence.

## Gaps / risks

- Version drift undermines all installer evidence until the package version, docs, and npm target agree.
- The validation plan still depends on local/manual execution for the most important release gates; this is acceptable only if the evidence artifact is explicit and durable.
- Existing `doctor` is not yet proven to be the future mutation-free preflight. Treat it as a health command until source and tests prove stricter behavior.
- Public mode is security-sensitive because full Hermes terminal toolsets remain enabled on `/workspace`; public validation must prove boundaries, not only service health.
- Funding policy persistence is not enough for delegated/scheduled runs; run-level funding decisions and receipts remain a separate product gate.
- Electron can simplify onboarding only if it makes cell ownership and runtime location explicit; otherwise it hides the same install risks behind a friendlier shell.

## Open questions for later passes

- Should `ReleaseEvidence` live under `docs/living-audit/`, `operations/releases/`, or a package-specific release folder?
- Should local package validation be a script that writes evidence, or a manual checklist first?
- Should the clean-install branch be validated from `npm pack` before `npx` publish, then repeated after npm publish?
- What is the minimum first-chat proof: HTTP transcript, UI screenshot, server log, or harness JSON?
- What backup artifact is required before reopening/updating an existing generated install?

## Next best planning target

Local vs Docker vs VPS deployment order: reduce the validation matrix into a single recommended deployment sequence and mode-selection state machine.