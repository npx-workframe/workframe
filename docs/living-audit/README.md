# Workframe Living Audit

Temporary planning/living-audit material for the path from the current Workframe repository to the Workframe v0.1.1 Softsupply strategy brief. This folder is not public release doctrine and should not be treated as implementation authority.

## Run 1 — installer decision tree

### Inspected source

- Repository: `npx-workframe/workframe`
- Branch/ref inspected: default branch `main`
- File evidence read directly from GitHub connector:
  - `README.md` blob `b97cd64e4f899dc758bb73a0e04ec9a89a344317`
  - `AGENTS.md` blob `f648f29fdb9569c3bb7a5c6c8e178173582cde03`
  - `START_HERE.md` blob `cf65246dc937256099d8297e79487635c3b724d2`
  - `.harness/README.md` blob `e21ce2d468b8f8baaa4660edf7054bd04d4f7ec0`
  - `.harness/feature_list.json` blob `ed32c988e668d813e99d8f332ebd2d22b3fbb95e`
  - `.harness/verify.mjs` blob `e8785ebc99091abfa295e9062613c4db208c840f`
  - `package.json` blob `7b8232a887d2c3558078c18cbbc6cac20051f363`
  - `packages/create-workframe/package.json` blob `72fc7bf7625c8e786baf0f9d44c389e5f4ad6547`
  - `docs/README.md` blob `e8a2a847ef29f784655f348fb1a53e535ff4915e`
  - `docs/public/install.md` blob `0ece45f99eb63781e090faefa670a61d3f33d265`
  - `docs/public/prerequisites.md` blob `1186fff652980860dbb18e30c267e7ac4844c910`
  - `docs/public/architecture.md` blob `df9acf46cad326df2a6e211dfd48608794ee42b4`
  - `docs/public/security.md` blob `3ab7a2408a92be7e8b6115bd798684b342cd5424`
  - `packages/create-workframe/bin/create-workframe.js` blob `3983e3e5e9110f406ab0f7a5d238a34c00c066f0`

### Current-state facts

- Public install entrypoint is `npx create-workframe@0.1.6 MyProject`, while package and monorepo versions are already `0.1.7`; install docs and README are version-drifted against package metadata.
- The current installer is explicitly Hermes-centered: the package description is "Scaffold a Workframe + Hermes workspace with guided onboarding", packaged keywords include `hermes`, and scaffold scripts pull/run the Hermes Docker image.
- Current install assumes Docker and Node as universal prerequisites. It does not yet describe an Electron-first path, a local native-runtime path, or adapter discovery for already-installed CLIs.
- Current generated layout creates a new `Agents/` and `Files/` tree. It deliberately avoids mounting the host Hermes home and treats bare Hermes default profile as not a Workframe install.
- Current wizard already distinguishes `single_user_local`, `trusted_team`, and `public_multi_user`, and already asks about BYOK/company-pays, SMTP, public URL, business profile, native agent, and invites.
- Current architecture docs define Workframe as a multi-user shell around Hermes, not yet as an adapter-first cell that can unify Hermes, Codex, Claude CLI, Cursor, OpenCode/OpenClaw, Copilot, and other runtimes.
- Current security posture already has useful primitives for the target product: secure mode, supervisor boundary, vault, per-turn leases, invite-only public mode, admin-only dashboard, and `user_only` provider behavior.
- Current harness covers API, provider model surface, public repo hygiene, web build, scaffold, UI bundle parity, and dogfood install-gate, but not multi-runtime detection or non-destructive adoption.

### Target-state mapping

The target installer should become a planner/wizard that selects a Workframe Cell shape before it starts mutating the filesystem.

The decision tree should be:

1. **Choose shell**
   - `npx create-workframe MyBusiness`
   - Electron app download
   - existing generated install opened again

2. **Detect environment**
   - OS: Windows, macOS, Linux, VPS Linux
   - Docker availability and Compose v2
   - Node availability
   - local browser availability
   - public domain/HTTPS posture
   - SMTP posture
   - existing Workframe install marker

3. **Detect existing agent/runtime assets without mutation**
   - Hermes install/home/profile availability
   - Workframe-generated `Agents/` tree availability
   - Claude CLI availability/auth posture
   - Codex/OpenAI auth posture
   - Cursor CLI/app presence, if detectable safely
   - Copilot/GitHub auth posture
   - OpenCode/OpenClaw availability
   - OpenRouter/OpenAI/Anthropic provider credentials only as metadata, never raw secret reads
   - Docker images/containers/volumes related to Workframe or Hermes

4. **Classify install branch**
   - `local_existing_runtime`: use existing Hermes/CLI/provider sessions through adapters, no overwrite.
   - `local_no_runtime`: create Workframe Cell and offer Hermes as default runtime.
   - `docker_existing_provider`: create Docker Workframe Cell and bind provider/CLI auth through brokered setup.
   - `docker_no_provider`: create Docker Workframe Cell and guide BYOK/provider connect before first chat.
   - `vps_public`: require domain, HTTPS, SMTP, generated secrets, invite policy, backups, and secure mode.
   - `team_trusted`: require invite policy and funding choice; allow LAN/trusted Docker posture.
   - `reopen_existing`: inspect manifest, preserve data, offer repair/upgrade only.

5. **Select runtime strategy**
   - If Hermes exists: adopt/import as an available runtime; never overwrite host Hermes state.
   - If no runtime exists: recommend Hermes as default starter runtime.
   - If multiple CLIs exist: register each as an optional EngineAdapter/RuntimeAdapter candidate.
   - If no CLI/provider is usable: finish UI/cell setup but block first agent run behind provider/runtime connect.

6. **Select funding policy**
   - Single user: BYOK default.
   - Trusted team: BYOK default, company-pays optional.
   - Public/VPS: BYOK default unless admin explicitly enables company keys/credits.
   - Hybrid: line-item funding source required per future run.

7. **Create first agent bindings**
   - Native concierge: default runtime/provider chosen during setup.
   - Architect agent: may use frontier model/provider/runtime.
   - Coder agent: may use code-specialized CLI/runtime.
   - Docs agent: may use local CLI or cheaper model route.
   - Every agent config stores desired engine/runtime/provider policy, not raw credentials.

8. **Launch minimum cell surfaces**
   - Files, browser, activity, kanban, goals, skills, slash commands, loops, agents, runs, and audit should appear regardless of runtime choice.
   - Runtime-specific capabilities may be disabled until the matching adapter is configured.

### Gaps and risks

- The product name/identity is still too coupled to Hermes in install/package wording. This is acceptable for v0.1.x only if the next plan introduces adapter vocabulary without a disruptive rewrite.
- The current installer is a scaffold generator, not yet an environment adoption wizard. Adding detection directly into the current monolithic installer risks making it brittle unless detection is separated into a small, testable preflight manifest.
- Non-destructive adoption is not yet represented as a first-class policy. The installer must never inspect or rewrite existing CLI secrets; it should record only presence, version, auth-ready status when safely available, and user-granted paths.
- The current generated layout owns `Agents/` and `Files/`; it does not yet model external runtime homes as read/adopt candidates.
- Current harness does not validate detection branches, existing-install reopen behavior, or multi-runtime agent profile configuration.
- Version drift between README/docs install command and package metadata can confuse the first install path.

### Proposed migration/refactor steps

1. Create a planning spec for a `workframe doctor --json` preflight report with no mutation.
2. Define `DetectedRuntime`, `DetectedProvider`, `DetectedInstall`, and `InstallPlan` data shapes before changing installer behavior.
3. Keep current Docker/Hermes path as `plan.kind = docker_hermes_default` and make all new branches additive.
4. Add non-destructive detection tests using fixture PATH/HOME directories; never require real user secrets in tests.
5. Add first-run wizard copy that says: "Workframe found these tools. Use them, ignore them, or install a default runtime."
6. Add `reopen_existing` path keyed by `workframe-manifest.json` so reruns repair/upgrade instead of overwriting.
7. Move agent runtime/provider choices into an adapter-oriented profile config plan, while preserving existing Hermes profile routing until the adapter seam exists.
8. Add harness scenarios for runtime detection map, existing install reopen, no-runtime install, and VPS prerequisites.

### Open questions for later passes

- Should Electron be only a shell around the local/VPS web UI first, or should it own local runtime detection and setup?
- Should `npx create-workframe` support a no-Docker local mode in v0.2, or should it remain Docker-first while Electron handles local-first?
- What is the minimum safe signal for "Codex/Claude/Cursor/Copilot auth exists" without reading private token files?
- Should existing host Hermes be adopted only as metadata, or can Workframe ever mount/link to it with explicit user consent?

### Next best planning target

Environment/runtime detection map: exact commands, files, safe probes, forbidden probes, and output schema for a mutation-free preflight report.
