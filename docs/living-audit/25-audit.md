# 25-audit — consolidated Workframe living audit

Temporary living-audit planning material. Not public release doctrine. This file consolidates the 24-run planning/red-team rail plus a fresh manual connector audit of the current `npx-workframe/workframe` codebase.

## Executive judgment

The 24-run rail was useful, but it was not an end-to-end codebase audit.

It produced strong strategic diagnostics around installer/product convergence, release truth, runtime adoption, authority gates, funding policy, and surface claims. It did not fully inspect every major source surface end to end, did not execute tests, did not run the installer, did not trace every API/UI path, and did not verify live Docker behavior.

The right characterization is:

```text
Good planning rail, not complete code audit.
Strong convergence diagnostics, incomplete implementation diagnostics.
Actionable enough to define the next implementation backlog, not enough to claim full system correctness.
```

## Fresh manual audit scope

Repository resolved directly: `npx-workframe/workframe`, default branch `main`.

Manual audit sampled these areas by direct GitHub connector reads:

| Area | Path | What was checked |
|---|---|---|
| Repo metadata | repository object | public repo, default branch, permissions, repo size |
| Package metadata | `package.json` | version, scripts, CI/test surface |
| Installer | `packages/create-workframe/bin/create-workframe.js` | target validation, generated compose, Hermes mounts, scripts, profile bootstrap, public overlay |
| Scaffold test | `packages/create-workframe/scripts/test-scaffold.mjs` | current scaffold coverage and negative project-name checks |
| Public docs | `README.md`, `docs/public/install.md`, `docs/public/architecture.md`, `docs/public/security.md`, `docs/public/api-reference.md` | public claims, install path, security model, surface map |
| Harness | `.harness/feature_list.json`, `.harness/verify.mjs` | cloud/local split and skipped release gates |
| API | `services/workframe-api/server.py`, `install_api.py`, `turn_credentials.py`, `credential_vault.py`, `llm_proxy.py` | secure mode, public-mode checks, invite gate, lease/vault/proxy model |
| Supervisor | `services/workframe-supervisor/server.py` | Docker/socket holder, profile lifecycle and host setup/update power |
| Living audit | `docs/living-audit/final-convergence-synthesis.md`, `package-truth-gate.md`, `red-team-12-evidence-authority-collapse.md` | planning convergence and final red-team pressure |
| Operator log | `operations/log.md` | confirmation that 24 runs created planning/red-team artifacts only |

## Assessment of the 24-run rail

### What it did well

The rail accurately converged on the central product problem:

```text
Workframe must prove one boring managed-Hermes package path before it expands into adapter-first/runtime-unifying claims.
```

It correctly identified:

- README/install version drift: public docs still advertise `create-workframe@0.1.6` while package metadata is `0.1.7`.
- Cloud-green is insufficient: `.harness/verify.mjs` skips manual and `cursor-local` scenarios.
- The release blocker is the packed package path, not source CI.
- Host runtimes should be detected-only, not adopted/executed.
- `open`, `update`, and `connect` are hidden-installer risks.
- Funding is credential authority, not billing metadata.
- Gates need evidence, owners, blockers, and negative tests.
- Workframe should not market the full OS surface before the five-panel spine has explicit contracts.

### What it did not do

The rail did not fully audit:

- every UI route/component under `apps/web/src/`;
- every API route implementation in `server.py`;
- every install script emitted by the generator;
- actual `npm pack` contents;
- actual clean install from tarball;
- actual Docker compose boot;
- actual setup wizard path;
- actual first managed-Hermes chat;
- actual public/VPS DNS/SMTP/HTTPS behavior;
- actual browser session/cookie behavior;
- actual negative install side-effect behavior;
- actual cross-user/profile/file isolation under a running stack.

The rail was therefore not blind, but it was source-sampling and doctrine-convergence, not exhaustive verification.

## Current-state facts from manual audit

### 1. Version drift is confirmed

Root package metadata is `0.1.7`, but public install copy still shows `npx create-workframe@0.1.6 MyProject` in both README and install docs.

Risk: users may install an older package while the repo/planning assumes newer behavior.

Severity: P0 release trust issue.

### 2. The harness cannot sign off release

Current `.harness/feature_list.json` has passing cloud-owned scenarios for API typecheck, SMTP/install surface, OAuth/LLM checks, provider model surface, public repo verify, web build, and installer scaffold.

But two release-critical scenarios are false/local-only:

```text
installer-ui-bundle = false, cursor-local
dogfood-install-gate = false, manual
```

`verify.mjs` skips manual checks and skips `owner: cursor-local`, so CI can pass without proving package UI parity or full install-gate.

Risk: green CI can mask a broken installable product.

Severity: P0 release blocker.

### 3. The scaffold test is strong but not sufficient

`test-scaffold.mjs` is more substantial than superficial smoke testing. It generates multiple packs, checks required files, verifies manifest shape, validates native profile naming, checks compose service names, checks that gateway does not bind host Hermes, checks public compose lacks docker.sock on API, checks proxy token/vault envs, validates lean `Files/`, checks bootstrap scripts, and rejects unsafe project names like `.`, `..`, `../escape`, and `bad/name`.

This is good.

But it does not prove:

- package tarball fidelity from `npm pack`;
- Docker pull/build/start success;
- wizard persistence;
- actual first chat;
- UI bundle identity;
- negative case non-mutation;
- no stale copied source artifacts.

Severity: P1. Scaffold tests should become one component of `PackageInstallEvidence`, not the release gate.

### 4. Installer is still generated-stack/Hermes-first

`create-workframe.js` still generates a Docker stack centered on managed Hermes. It creates `Agents/` and `Files/`, mounts `./Agents:/opt/data`, mounts `./Files:/opt/data/workspace`, pulls Hermes image, writes routes, creates profiles, and emits scripts for bootstrap/install/chat.

This is correct for v0.1.x if positioned honestly.

But it means current implementation does not yet support real adapter-first execution. Runtime unification should remain detection/planning only until a second adapter harness exists.

Severity: P1 product-claim risk.

### 5. Installer target safety is partially addressed

`validateProjectName` rejects path separators, absolute paths, `.` and `..`, and unsafe names. `resolveProjectTarget` ensures target stays under output root.

This is good.

Unverified/remaining:

- non-empty target behavior under normal non-`--force` path;
- whether denial guarantees no mutation;
- whether existing Workframe cell is detected distinctly from arbitrary non-empty folder;
- whether recovery text is clear.

Severity: P0 for release evidence; P1 for UX.

### 6. Public multi-user security posture exists but should not be overclaimed

Docs and code include real public-mode controls:

- `SECURE_MODE=true` default posture;
- `DEV_LOCAL_UNSAFE` mutually exclusive with secure mode;
- public mode requires supervisor URL/token, auth keys, API token, SMTP, HTTPS app base URL, vault KEK, proxy token;
- public mode rejects docker.sock on `workframe-api`;
- invite-only login after install;
- public docs state only supervisor should mount docker.sock.

This is substantial.

But generated base compose still mounts broad `Agents/` and `Files/` into API/gateway/supervisor, and public multi-user isolation relies on profiles, API checks, supervisor guards, and credential vault rather than hard filesystem isolation.

Severity: P1. Acceptable only if documented as constrained/trusted-public posture, not enterprise isolation.

### 7. Credential architecture is directionally strong

Manual audit confirms:

- `credential_vault.py` implements API-side envelope encrypted secret storage.
- `turn_credentials.py` issues `wf_rt_` opaque turn leases with payer, workspace, provider, credential binding, profile slug, expiry, and revocation.
- `llm_proxy.py` validates lease/provider/profile and resolves upstream access server-side.

This supports the living-audit claim that Workframe already has the seed of a capability/lease model.

Remaining gap: `RunAuthorityGate` is not yet a first-class product primitive over all runtime/tool actions. The current lease mechanism is LLM-centric.

Severity: P1 architecture gap, not blocker for single-user v0.1.x if scoped.

### 8. Supervisor boundary is powerful and risky

`workframe-supervisor` is the Docker/socket holder and can run compose updates, restart gateway, start device OAuth, and execute privileged host setup for public HTTPS through Docker/chroot.

This is the correct place for dangerous host/Docker actions, not the API.

But this means supervisor routes need strict evidence, auth, denial tests, and public-mode constraints. The living-audit concern about hidden installers is valid.

Severity: P1 for internal/trusted mode; P0 before public install claims.

### 9. Docs describe more than the release can prove today

Public docs position Workframe as multi-user and describe setup branches for single-user, trusted team, and public multi-user. The architecture docs describe chat, files, browser, activity, rooms, credentials, provider connect, session binding, and Hermes proxy routes.

Some of this is implemented, but the release evidence does not yet prove the end-to-end journeys.

Severity: P0 docs-claim gate for next release.

## Consolidated findings

### P0 — release blockers

1. **Version agreement gate**
   - README, install docs, package metadata, npm version, and tag must agree.
   - Evidence: root package is `0.1.7`; README/install docs still show `0.1.6`.

2. **PackageTruthGate implementation**
   - Must run from packed artifact, not source tree optimism.
   - Must produce machine-readable release evidence.

3. **Split evidence model**
   - Use `PackageInstallEvidence`, `FirstRunEvidence`, and `NegativeInstallEvidence` sections.
   - Avoid one overloaded `first_chat_ok` boolean.

4. **Empty-target-only release claim**
   - Until `CellAuthorityGate` exists, public install claim should be clean empty target only.
   - Existing directory must deny with no mutation.

5. **Local-only release gates cannot be skipped silently**
   - `.harness/verify.mjs` may skip local scenarios for cloud CI, but release sign-off must fail or report blocked when local evidence is missing.

6. **Docs-claim gate**
   - README/install/release docs must only claim what evidence proves.
   - Public/VPS/team/company-pays/adapter execution should be marked planned/manual/experimental unless evidence exists.

### P1 — next implementation priorities

7. **CellAuthorityGate**
   - Manifest provenance.
   - Install root ownership.
   - Recognized data dirs.
   - Read-only open.
   - Explicit mutation plan before update/connect/adopt.

8. **Mutation-free doctor**
   - `workframe doctor --json` should report Docker/Node/cell/managed-Hermes/host-runtime candidates/provider candidates without reading private credential material or mutating host state.

9. **RunAuthorityGate**
   - One pre-run decision over actor, profile owner, runtime, provider, credential binding, funding mode, payer, delegation authority, allow/deny reason.

10. **SurfaceContractGate**
   - Agent rail, chat, files, browser, activity need contracts: reads, writes, authority gate, evidence emitted.

11. **Supervisor negative tests**
   - Public mode cannot access docker.sock from API.
   - Supervisor rejects profile/path misuse.
   - Stack update/connect actions require explicit authority.

12. **UI/package parity identity**
   - Generated UI should expose build/package identity so package evidence can assert bundled UI parity.

### P2 — v0.2 architecture work

13. **AgentIdentity vs HermesRuntimeState seam**
   - Separate Workframe agent identity from Hermes profile implementation.

14. **RuntimeBinding candidate model**
   - Represent host Hermes, Codex, Claude CLI, Cursor, Copilot, OpenCode/OpenClaw as inert candidates.
   - Do not execute until adapter harness proves start/stream/cancel/log/receipt.

15. **Second runtime adapter harness**
   - Pick one non-Hermes adapter later and prove it end-to-end before expanding matrix.

16. **Funding modes beyond BYOK**
   - Company-pays and hybrid require visible payer, no `user_only` fallback, and receipt evidence.

17. **Public/VPS hardening**
   - Domain, HTTPS, SMTP, invite-only, backup/restore, and secure-mode evidence before marketing public mode.

## What was missing from the 24-run rail

The rail lacked a code-owner style file-by-file audit for:

- UI components and state transitions;
- API route handlers beyond sampled security/lease/install surfaces;
- generated shell/PowerShell scripts beyond generator snippets and scaffold checks;
- desktop/Electron code;
- update scripts;
- backup/restore path;
- browser panel implementation;
- activity/receipt implementation;
- slash command execution;
- Kanban/goals/skills/loops behavior;
- exact PR/issue state.

Those gaps matter. They should become separate implementation/debugging audits after `PackageTruthGate` is built.

## Recommended implementation backlog

### Ticket 1 — Add release evidence schema

Create a schema under a maintainer-owned path such as:

```text
operations/release-evidence/schema/package-truth-gate.schema.json
```

Fields:

- gate name/version;
- git ref;
- package version;
- package tarball digest;
- target mode;
- step assertions with `asserted | not_asserted | failed`;
- redacted commands;
- redacted outputs;
- negative cases with mutation observed false;
- decision and reason.

Definition of done:

- schema committed;
- example evidence fixture committed;
- docs say evidence is maintainer-release artifact, not product audit.

### Ticket 2 — Build package install evidence runner

Add a script that:

```text
pnpm install
pnpm build:web
node packages/create-workframe/scripts/bundle-workframe-ui.mjs --skip-build
npm pack packages/create-workframe
create clean temp target from tarball
assert required generated files
assert manifest/package version
assert UI asset/build identity if available
```

Definition of done:

- produces JSON `PackageInstallEvidence`;
- fails on version drift;
- does not require live model key.

### Ticket 3 — Build negative install evidence runner

Cases:

- non-empty target deny;
- unsafe project name deny;
- existing arbitrary directory deny/no mutation;
- existing Workframe manifest read-only detection;
- missing Docker returns needs-user-action, not partial install.

Definition of done:

- every negative case records mutation hash before/after;
- no side effects outside temp dir.

### Ticket 4 — Build first-run evidence runner

Manual/local first if needed.

Proves:

- Docker compose boot;
- API health;
- supervisor health;
- managed Hermes health;
- wizard complete for `single_user_local`;
- explicit BYOK credential path;
- first chat returns or streams;
- minimal activity/session/receipt evidence exists.

Definition of done:

- produces `FirstRunEvidence` JSON;
- uses redacted credential source class only;
- does not import host CLI auth.

### Ticket 5 — Version agreement verifier

Script checks:

- root package version;
- `packages/create-workframe/package.json` version;
- README install command;
- `docs/public/install.md` install command;
- optional release doc/tag expectations.

Definition of done:

- CI can run it;
- release gate fails on drift.

### Ticket 6 — Docs claim gate

Add a small verifier that scans public docs for claims outside current evidence scope.

Initial deny/flag patterns:

- Electron setup as supported;
- Codex/Claude/Cursor execution as supported;
- public VPS production-ready if no evidence;
- company-pays execution if no RunAuthorityGate evidence;
- adapter-first execution before second harness.

Definition of done:

- flags unsupported claims;
- allows planned/experimental wording.

### Ticket 7 — Define CellAuthorityGate design doc

No code required initially.

Must specify:

- manifest provenance fields;
- read-only open state;
- update/connect/adopt blocked states;
- destructive action plan format;
- recovery text.

Definition of done:

- implementation tickets can be derived.

### Ticket 8 — Define RunAuthorityGate design doc and tests

Must specify:

- single-user BYOK;
- trusted-team BYOK delegation;
- company-pays opt-in;
- user-only provider no fallback;
- deny reason semantics.

Definition of done:

- test cases listed before implementation.

## Final answer to the user question

No: the 24 runs did not accurately investigate the whole codebase end to end.

Yes: they delivered high-quality actionable diagnostics for the product/release architecture layer.

They were strongest on:

- install path strategy;
- release gates;
- runtime adoption policy;
- funding/credential authority;
- product-claim discipline.

They were weakest on:

- actual execution;
- full UI/API route coverage;
- generated script behavior;
- live Docker/package verification;
- edge-case security testing.

The correct next step is not another broad planning loop. It is implementation of the `PackageTruthGate` evidence spine, followed by targeted code audits where the evidence fails.
