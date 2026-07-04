# Deployment order and mode-selection state machine

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
| Public deploy checklist | `infra/compose/workframe/PUBLIC_DEPLOY.md` | `2a6ec3188a5e75023b2a11aeaed778e06c12d6da` |
| Installer | `packages/create-workframe/bin/create-workframe.js` | `3983e3e5e9110f406ab0f7a5d238a34c00c066f0` |
| Prior validation pass | `docs/living-audit/installer-validation-plan.md` | `cf2b297851d0f6b0c4f8726984b9ae8b70f1fb8f` |
| Prior red-team pass | `docs/living-audit/red-team-06-validation-matrix-risk.md` | `3968385e4685f419751f8217c1d384303bb10308` |
| Operator log | `operations/log.md` | `0df4226f51a2d550da0c1d99c6b0db514f4eee43` |

## Planning slice

Local vs Docker vs VPS deployment order: reduce installer validation into one safe mode-selection sequence that does not confuse scaffold success, cell health, first chat, public launch readiness, Electron convenience, or adapter execution.

## Current-state facts

- Public README and install docs still advertise `npx create-workframe@0.1.6`, while monorepo and installer package metadata are `0.1.7`.
- The documented end-user path is scaffold project, optional doctor, `docker compose up -d --build`, setup wizard, then launch.
- Install docs define three modes: `single_user_local`, `trusted_team`, and `public_multi_user`; `.env` deployment mode wins over stack config after restart.
- Architecture docs define Workframe today as a multi-user shell around Hermes with UI, API, supervisor, gateway, shared `Agents/`, shared `Files/`, vault, and per-user runtime profiles.
- Security docs and public deploy docs require public mode to prove HTTPS, SMTP, secure mode, vault/proxy/supervisor secrets, dashboard gating, env allowlisting, and no API Docker socket.
- Harness cloud checks skip local-only and manual gates; `installer-ui-bundle` and `dogfood-install-gate` remain false local/manual checks.
- Installer source validates project basename, can reject path escape, writes a generated Docker/Hermes cell, defaults CLI project-name runs to forceful behavior, starts a UI-first install script, and removes an existing target when force is true.
- Generated install scripts already describe a two-phase path: scaffold, then UI-first Docker stack plus native Hermes bootstrap.

## Target-state deployment order

Workframe should present one canonical sequence with mode-specific gates, not three unrelated installers.

```text
0. Resolve intent
   create_new_cell | open_existing_cell | update_existing_cell | connect_remote_cell

1. Preflight only
   OS, Node, Docker, ports, target folder, existing Workframe manifest, existing runtime markers.
   No secrets read. No host runtime adoption. No destructive write.

2. Choose mode
   single_user_local   -> loopback Docker/Hermes cell, no SMTP required.
   trusted_team        -> Docker/LAN cell, invite policy, BYOK default.
   public_multi_user   -> VPS/public URL, HTTPS + SMTP + generated secrets before launch claim.

3. Create or reopen cell
   new target: scaffold generated project.
   existing target: refuse destructive overwrite; offer open/update/backup path.

4. Boot current supported runtime
   Hermes-in-Docker remains default runtime for v0.1.x.
   Other runtimes are detected as candidates only.

5. Complete wizard
   owner/admin, business profile, provider/funding choice, native agent, first chat.

6. Validate mode posture
   local_package_gate for local release truth.
   team_install_gate before invited team usage.
   public_launch_gate for every public VPS deployment.
```

## Mode-selection state machine

| State | User-facing question | Safe default | Blocking gate | Deferred claim |
|---|---|---|---|---|
| `create_new_cell` | Are you creating a new Workframe cell? | Yes for `npx create-workframe MyBusiness` | Target must be absent or empty enough to scaffold safely. | Existing host Hermes/CLI adoption. |
| `open_existing_cell` | Is this already a Workframe folder? | Reopen if `workframe-manifest.json` exists. | Must not overwrite `Agents/`, `Files/`, `.env`, API data, or vault. | Update/migration until backup gate exists. |
| `single_user_local` | Is this only for you on this machine? | Loopback Docker/Hermes. | Docker available, ports allocated, UI bundle present, wizard and first chat pass. | SMTP, public URL, team billing. |
| `trusted_team` | Is this a LAN/small-team cell? | BYOK default, invite-only. | Admin identity, invite path, provider policy saved, no `user_only` fallback. | Billing-grade run receipts. |
| `public_multi_user` | Is this reachable on a public domain? | Fail closed until HTTPS/SMTP/secrets are proven. | Live public gate: HTTPS `APP_BASE_URL`, SMTP, vault/proxy/supervisor tokens, dashboard RBAC, gateway env check, network separation. | Persistent `public_ready` boolean. |
| `connect_remote_cell` | Are you opening a remote VPS from Electron/desktop? | Connect only; do not create locally. | URL/session trust and cell ownership shown clearly. | Desktop as installer proof. |
| `adapter_candidate` | Did we detect Claude/Codex/Cursor/OpenCode/etc.? | Marker-only inventory. | Redacted, consented, no auth import. | Runtime execution through non-Hermes adapters. |

## Gaps / risks

- The public docs and package metadata version drift must be corrected before release evidence can be trusted.
- `--force` and positional project-name behavior are high-risk for existing folders; release truth needs a no-overwrite/sentinel gate before promotion.
- Public launch posture is environment-specific; it should never be inferred from local Docker health or first chat.
- Electron can improve UX only after the CLI cell contract is safe; otherwise it hides create/open/connect/update decisions.
- Provider credential success must remain distinct from runtime adapter readiness.
- Team funding mode can be persisted early, but billing-grade delegation requires later run-level funding decisions and receipts.

## Proposed migration / refactor steps

1. Make documentation and release planning use four verbs consistently: `create`, `open`, `update`, `connect`.
2. Treat Docker/Hermes local cell as the only release-blocking v0.1.x execution path.
3. Add a mandatory existing-target sentinel validation before any installer promotion.
4. Split gates explicitly: `local_package_gate`, `team_install_gate`, `public_launch_gate`, `electron_shell_gate`, `second_adapter_gate`.
5. Keep runtime detection read-only and redacted until the `PreflightRedactionGate` exists.
6. Require public VPS verification to be live and timestamped per deployment, not a stored readiness flag.
7. Define Electron as a cell selector first: create local cell, open local cell, or connect remote cell.

## Open questions for later passes

- Should `doctor` become the canonical preflight command, or should a separate `preflight` command exist to guarantee no mutation?
- What exact sentinel files prove existing-target no-overwrite safety across `Agents/`, `Files/`, `.env`, manifest, and API data?
- Should update posture be blocked until backup/restore is scripted, or documented as manual for v0.1.x?
- Which public deploy evidence should be machine-readable versus operator checklist?

## Next best planning target

Existing-runtime adoption policy: specify what can be detected, what can be displayed, what requires consent, and what must never be imported or mounted during v0.1.x.