# Workframe surface baseline

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
| Using docs | `docs/public/using-workframe.md` | `20ee82af97dc8aee9967eea768172d253471eca9` |
| API docs | `docs/public/api-reference.md` | `8ac837776545924e941b3660f1938406f2a4d23c` |
| Architecture docs | `docs/public/architecture.md` | `df9acf46cad326df2a6e211dfd48608794ee42b4` |
| Security docs | `docs/public/security.md` | `3ab7a2408a92be7e8b6115bd798684b342cd5424` |
| App shell | `apps/web/src/App.tsx` | `dd15273f836db746062594e91446d70dc1f6aae9` |
| Workspace layout | `apps/web/src/components/workspace/DockviewWorkspace.tsx` | `1d5a7bbca7079492f859ea1cdc668efd4780aca2` |
| Panel controls | `apps/web/src/lib/panelControlConfig.ts` | `2ce0892d3225f362fcb3099af952cea3da830dd1` |
| Previous planning slice | `docs/living-audit/existing-runtime-adoption-policy.md` | `563631b5e23b8d608c0a7cf3e21f8c7371d6093f` |
| Operator log | `operations/log.md` | `bc98fb2ebf79e13612777df341f9bbe29a51daf3` |

## Planning slice

Workframe files/browser/activity/kanban/goals/skills/slash-command baseline: define the minimum surface contract that works across single-user local, Docker, VPS, and later adapter-first setups while v0.1.x executes only managed Hermes Docker.

## Current-state facts

- Product entry remains `npx create-workframe`; README describes Workframe as UI, API, installer, and Docker Compose around Hermes.
- Generated installs contain `Agents/`, `Files/`, API, UI, supervisor, compose, and `workframe-manifest.json`.
- Architecture docs define the visible UI as chat, files, browser, and activity, with API as same-origin backend and Hermes as profile/session/runtime provider.
- The current workspace UI initializes five dock panels: agent rail, chat, files, browser, and activity.
- Public docs promise rooms/spaces, DMs, activity, files, browser panel, team rail, chat, create agent, model picker, skills, slash commands, profile/account connection, stack keys, Hermes dashboard, @mentions, agent DMs, and Kanban.
- API docs expose routes for members/invites/rooms/messages/live events, Hermes profile bind/chat/models/skills/commands/profile creation, file tree/read/write/upload, and health.
- Security docs make BYOK default, `user_only` providers no-fallback, vault, leases, supervisor separation, invite-only public mode, and per-user runtime profile isolation part of the surface boundary.
- Harness evidence is backend/install-gate focused; UI dogfood is local-only, and full install-gate remains manual/local.
- Previous planning narrowed host runtime adoption to redacted inert candidates; only Workframe-managed Hermes Docker is executable for v0.1.x.

## Surface principle

Workframe should not ship a broad agentic OS by label. It should ship a small cell where every visible surface either:

1. Works now against managed Hermes Docker and Workframe-owned state.
2. Clearly displays read-only or not-configured state.
3. Is hidden behind an explicit unavailable/coming-later gate.

No visible surface should imply that host Claude/Codex/Cursor/Copilot/OpenCode adapters can run until an adapter harness proves execution, cancellation, logs, receipts, and credential boundaries.

## Baseline surface contract

| Surface | v0.1.x minimum | Runtime dependency | Should work when no provider key? | Evidence gate |
|---|---|---|---:|---|
| App boot | Resolve install/auth/onboarding/shell without loop or ambiguous state. | Workframe API | Yes | install-window + restore-session smoke |
| Agent rail | Show native/managed agent lane and profile state. Disable inert adapter candidates. | Hermes profile catalog | Yes | agent lane renders without first chat |
| Chat / runs | Bind to managed Hermes profile, stream, stop, steer, and show error if no key. | Managed Hermes Docker | No run; UI still works | first chat smoke + no-key error smoke |
| Files | Tree/read/write/upload under generated `Files/` only. | Workframe API + workspace mount | Yes | file tree/read/write roundtrip |
| Browser | Preview workspace artifacts, especially files created under `Files/`. | Files surface | Yes | open generated HTML/Markdown artifact |
| Activity | Show room/agent/run/file events from Workframe state. | Workframe API events | Yes | event appears after file/chat action |
| Kanban | Expose Hermes Kanban as execution state, but preserve files as truth. | Hermes profile state | Partial | create/read/update card smoke or hide if absent |
| Goals | Treat as durable file-backed planning artifacts before a separate database product surface. | Files + optional Kanban | Yes | goal doc template appears in Files |
| Skills | List/attach Hermes skills only for managed Hermes; non-Hermes skill compatibility stays inert. | Hermes skills API | Yes for listing; no for run | list skills + disabled attach without runtime/key |
| Slash commands | Display command catalog; execute only allowlisted managed-Hermes commands. | Hermes command API + policy | Partial | command catalog + blocked unsafe command |
| Loops | Show scheduled/loop plans as audit-visible artifacts; do not create autonomous hidden loops by default. | Files/Kanban/audit first | Yes | loop plan artifact + explicit enable gate |
| Agents | Create managed Hermes profile from templates; adapter profiles are config-only until validated. | Supervisor + Hermes | Provider needed for useful run | profile create + bind smoke |
| Audit | Every install/setup/run/mutation-adjacent action emits a human-readable event/receipt. | Workframe API | Yes | release evidence artifact + event stream |
| Provider settings | BYOK/company-pays/hybrid choice visible without raw secret exposure. | Vault/lease path | Yes | redacted provider status smoke |
| Admin/team | Invite/domain/SMTP/company-pays controls are visible only in team/public modes. | Workframe API + SMTP | Yes | mode-gated controls smoke |

## Target-state mapping

### Single-user local

```text
create cell
  -> first-run wizard
  -> managed Hermes profile
  -> connect provider or show no-key state
  -> baseline panels load
  -> first chat/file/browser/activity proof
```

Keep rooms/team/admin mostly hidden or reduced to local identity. Do not require SMTP. Do not surface host runtime adoption except as inert inventory in preflight/doctor.

### Docker user with provider auth but no Hermes

```text
create Docker cell
  -> provider setup through Workframe vault
  -> managed Hermes runtime starts inside cell
  -> agent rail/chat/files/browser/activity prove product loop
```

Provider auth is not a runtime. The visible product must prove managed runtime plus Workframe-owned file/audit surfaces.

### Empty machine

```text
doctor/preflight
  -> missing Docker/Node/provider guidance
  -> create default managed Hermes cell when prerequisites exist
  -> launch shell with no-key and no-runtime states explicit
```

Do not make blank-state UX look broken. The product should show exactly what is missing and which surfaces are still usable.

### VPS/self-hosted

```text
public mode
  -> domain/HTTPS/SMTP/secrets/invite policy gates
  -> admin setup
  -> team members invited
  -> shared surfaces visible with per-user runtime/profile boundaries
```

Admin/team surfaces must be mode-gated. Local host runtime detection is irrelevant to server execution.

### Multi-user funding

```text
run request
  -> actor + agent + workspace + provider policy
  -> BYOK/company/hybrid decision
  -> runtime lease
  -> run receipt shown in audit/activity
```

Funding policy must be visible before a run and auditable after a run. Do not bury it in model picker behavior.

## Product-level contradictions to resolve

- Docs promise many surfaces, but current harness only proves a subset. Release messaging should distinguish `available`, `preview`, `Hermes-backed`, and `planned` surfaces.
- Kanban is described as execution state and project truth stays in files, but UI baseline must prevent users from treating Kanban as canonical product memory.
- Skills and slash commands are listed as Workframe-native surfaces but are currently Hermes-shaped; v0.1.x should call them managed-Hermes skills/commands unless/until adapter-neutral semantics exist.
- Activity is a core surface, but release evidence must define what events are emitted. Otherwise it risks becoming a decorative panel.
- Agent rail can imply many executable agents/runtimes. v0.1.x must separate `agent identity`, `runtime binding`, `provider policy`, and `execution availability` in the UI.
- Browser/files can imply broad filesystem authority. The baseline must restrict them to generated `Files/` and explicit workspace mounts.

## Proposed migration / refactor steps

1. Define `SurfaceAvailability` with states: `available`, `not_configured`, `runtime_required`, `admin_required`, `mode_gated`, `planned`.
2. Add a visible surface matrix to release docs before expanding code: each surface needs one evidence gate.
3. Treat the five existing panels as the v0.1.x product spine: agent rail, chat, files, browser, activity.
4. Collapse goals/loops into files + activity + optional Kanban until dedicated domain models exist.
5. Rename or label skills/slash commands as managed-Hermes capabilities in v0.1.x UI copy/docs.
6. Require a `RunReceipt` shape before second-runtime execution: runtime, provider policy, funding policy, credential boundary, files touched, commands run, start/stop state.
7. Add release evidence for shell boot, panel render, no-key state, first chat, file roundtrip, browser preview, and activity event.
8. Defer generic adapter surfaces until a second runtime passes adapter harness and can produce the same run receipt.
9. For public mode, require proof that user A cannot see user B credentials/profile state through files, activity, commands, or dashboard proxy.
10. For Electron, show whether each surface is connected to local cell, remote cell, or offline project; never blend local host inventory with remote server authority.

## Minimal v0.1.x surface promise

```text
A Workframe cell gives you:
  - a guided first-run setup
  - one managed Hermes-backed agent lane
  - chat with explicit no-key/provider state
  - project files under Files/
  - browser preview of workspace artifacts
  - activity/audit events for meaningful actions
  - managed-Hermes skills and slash-command catalog where safe
  - optional team/admin setup gates for trusted/public modes

It does not yet promise:
  - execution through host Claude/Codex/Cursor/Copilot/OpenCode
  - adapter-neutral skills
  - billing-grade company-pays receipts
  - autonomous loops without explicit enablement
  - host filesystem access beyond the generated workspace
```

## Open questions for later passes

- Which exact activity events should be release-blocking: install completed, provider connected, profile created, chat started, chat stopped, file written, invite sent?
- Should goals be plain files, Kanban cards, or first-class API objects in v0.2?
- Should slash-command execution be entirely disabled in public multi-user until command allowlists and receipts exist?
- What is the smallest proof that Files/Browser cannot escape the generated `Files/` tree?
- Should the UI show inert runtime candidates inside agent rail, settings, or only preflight/doctor output?

## Next best planning target

Multi-user/BYOK/company-pays journey: define the smallest funding and credential policy that makes team use understandable without implementing billing-grade receipts yet.
