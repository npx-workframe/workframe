# First-run wizard convergence map

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
| Installer | `packages/create-workframe/bin/create-workframe.js` | `3983e3e5e9110f406ab0f7a5d238a34c00c066f0` |
| Install docs | `docs/public/install.md` | `0ece45f99eb63781e090faefa670a61d3f33d265` |
| Architecture docs | `docs/public/architecture.md` | `df9acf46cad326df2a6e211dfd48608794ee42b4` |
| Security docs | `docs/public/security.md` | `3ab7a2408a92be7e8b6115bd798684b342cd5424` |
| Session docs | `docs/public/session-architecture.md` | `65481ee7cac21e4575b3284be7a6d5d2bdcd1c62` |
| Product surfaces | `docs/public/using-workframe.md` | `20ee82af97dc8aee9967eea768172d253471eca9` |
| VPS checklist | `infra/compose/workframe/PUBLIC_DEPLOY.md` | `2a6ec3188a5e75023b2a11aeaed778e06c12d6da` |
| API | `services/workframe-api/server.py` | `52e962760c28ad0eb70240287ed49aa746d3767b` |
| Install API | `services/workframe-api/install_api.py` | `b204c25a0916083e20947ae395c3f827e08a3d44` |
| Supervisor | `services/workframe-supervisor/server.py` | `2ffcbfd84da421f59b62bb371f08fc727b560f70` |

## Planning slice

First-run wizard journey: how `npx create-workframe MyBusiness` or an Electron shell should converge to a working Workframe cell without forcing product identity to be Hermes and without destructive adoption of existing runtimes.

## Current-state facts

- Public docs and README still advertise `create-workframe@0.1.6`; package metadata is `0.1.7`.
- Current product identity in docs is a multi-user shell around Hermes; installer package description is explicitly `Workframe + Hermes`.
- The generated install creates `Agents/` runtime state and `Files/` workspace truth, then mounts them into Docker services.
- The current UI-first install path opens `/install`, starts Docker, bootstraps a native Hermes profile, and then expects onboarding in the browser.
- Current setup wizard docs already define owner/admin mode choice, public URL, SMTP/admin verification, integrations, model billing, business profile, user profile, model keys, native agent, invites, and launch.
- Current API install status is primarily keyed by native Hermes presence plus setup completion.
- Public/VPS hardening already requires HTTPS, SMTP, vault/proxy/supervisor secrets, invite-only auth, admin dashboard gating, and no Docker socket on API.
- Per-user runtime profiles are already documented as `u-{user}-{agent}` clones with vault-managed credentials and lease tokens.

## Target-state first-run state machine

```text
ENTRY
  ├─ npx create-workframe MyBusiness
  └─ Electron app download/open existing cell

PRELIGHT: read-only detection
  ├─ OS / shell / browser / Node / Docker / Compose / ports
  ├─ existing Workframe manifest + install_complete
  ├─ existing Hermes home/profile(s) metadata only
  ├─ existing agent CLIs: Claude, Codex, Cursor, OpenCode/OpenClaw, Copilot
  ├─ provider auth posture: OpenAI/Codex OAuth, OpenRouter, Anthropic, GitHub, Vercel
  └─ public-host posture: domain, HTTPS, SMTP, backups

PLAN: choose cell shape before mutation
  ├─ single_user_local
  ├─ trusted_team
  ├─ public_multi_user
  ├─ reopen_existing
  └─ repair_or_upgrade_existing

RUNTIME STRATEGY
  ├─ adopt_existing_runtime_adapter(s), no overwrite
  ├─ create_isolated_docker_hermes_default
  ├─ bind_provider_auth_to_runtime_profile
  └─ defer_runtime_until_first_agent_chat

FUNDING STRATEGY
  ├─ BYOK default
  ├─ company-pays admin opt-in
  └─ hybrid: user_only providers never workspace-fallback

PROFILE STRATEGY
  ├─ template agent: architect / coder / docs / research / designer
  ├─ per-user runtime: u-{user}-{agent}
  ├─ runtime adapter: hermes | codex | claude | cursor | opencode | copilot | custom
  └─ provider/model: independent from agent role

LAUNCH GATE
  ├─ can open Workframe UI
  ├─ can connect provider or adopt OAuth session safely
  ├─ can create/bind one runtime profile
  ├─ can send first agent message
  └─ records install manifest + audit event
```

## Target user journeys

### 1. Local user already has Hermes and Claude/Codex/other CLI

Read-only detection should produce an adoption report, not copy files. The wizard should ask which assets to expose as adapters. Existing Hermes host state remains off-limits unless the user explicitly creates a Workframe-managed binding. Claude/Codex/Cursor/OpenCode/Copilot should be represented as runtime adapters with capability/auth status, not as provider keys to scrape.

Minimum launch: create a Workframe cell, keep `Files/` as workspace truth, create adapter records, and bind the first agent profile to the chosen runtime. If Hermes is selected, prefer isolated Docker Hermes unless the user explicitly chooses host Hermes adoption.

### 2. Docker user has no Hermes but has OpenAI/Codex/OpenRouter/Anthropic credentials

The wizard should treat Docker as the cell substrate and credentials as provider posture. It should create an isolated Workframe cell, offer Hermes as default runtime, and bind provider auth through vault/lease mechanics. It should not equate `has OpenAI auth` with `has runtime`; runtime creation and provider funding are separate decisions.

### 3. User has nothing installed

Recommended path: install Docker or choose Electron-managed local runtime path; create Workframe cell; default runtime is Hermes because it is the current packaged working path, but copy must say `default starter runtime`, not `the product`.

### 4. VPS/self-hosted user

The wizard must fail closed before public launch if HTTPS, SMTP, vault/proxy/supervisor secrets, invite policy, and backup posture are missing. It should distinguish `trusted_team` LAN from `public_multi_user` and should not use loopback health as evidence of public readiness.

### 5. Multi-user team

Funding decision must happen before inviting users: BYOK default, company-pays admin opt-in, or hybrid. `user_only` providers remain non-fallback even in company-pays mode. The agent assignee/runtime owner is the billing owner for delegated work.

## Gaps / risks

- Product copy and package metadata still frame the install as `Workframe + Hermes`, while target doctrine needs Workframe as the cell and Hermes as one runtime adapter.
- Current scaffold path may remove an existing target directory with `--force`; target-state adoption needs a non-destructive `inspect/reopen/repair` branch before any destructive write.
- The current native deploy branch only detects Hermes home and errors if missing; it does not yet model multiple runtime adapters or safe CLI adoption.
- Current install status uses native Hermes presence as a major readiness signal; adapter-first readiness should track `cell_ready`, `workspace_ready`, `runtime_bound`, `provider_ready`, and `first_chat_verified` separately.
- Harness scenarios cover current scaffold and CI surfaces, but not the target decision tree, read-only detection report, adapter binding, no-overwrite adoption, VPS readiness gate, or multi-user funding behavior.
- README/install version drift is release-readiness debt, but should be fixed in a release/doc cleanup pass, not inside this planning rail.

## Proposed migration / refactor steps

1. Define `workframe-manifest.json` v2 planning schema: cell id, install mode, funding policy, workspace paths, runtime adapters, provider posture, public-host posture, and last validation gates.
2. Add read-only environment detection module under installer scripts. It must return facts only; no filesystem mutation, no credential reads, no host Hermes writes.
3. Split installer flow into `detect -> plan -> confirm -> mutate -> validate` phases. Existing scaffold generation becomes only the mutate phase.
4. Introduce runtime adapter records independent from Hermes profile config: `runtime_id`, `kind`, `scope`, `auth_status`, `workspace_mount`, `can_stream`, `can_run_tools`, `risk_notes`.
5. Change first-run API status vocabulary from Hermes-centric phases to cell-centric gates while preserving current Hermes fields for compatibility.
6. Keep Hermes as the default runtime path for empty installs until at least one non-Hermes adapter has an end-to-end green validation gate.
7. Add installer tests for: empty local install, existing target reopen, host Hermes detected no overwrite, Codex auth detected no secret read, VPS missing SMTP fail-closed, BYOK/company/hybrid policy persisted, and first-chat smoke.
8. Only after tests exist, adjust public docs from `multi-user shell around Hermes` toward `Workframe cell with Hermes default adapter`.

## Validation gates for this slice

| Gate | Evidence required |
|---|---|
| Detection is read-only | Fixture test proves target and existing runtime homes unchanged. |
| Empty install still works | Current `installer-scaffold` plus first-chat smoke stays green. |
| Existing install is not overwritten | Existing manifest causes `reopen_existing` unless explicit repair/upgrade chosen. |
| Host Hermes is not touched by default | Detection reports metadata only; no mount/copy/write without explicit confirmation. |
| Provider secrets are not read | Detection reports presence/auth posture only. |
| Public VPS is fail-closed | Missing HTTPS/SMTP/secrets blocks `public_multi_user` launch. |
| Funding policy is explicit | BYOK/company/hybrid persisted before invites. |

## Open questions for later slices

- What is the exact minimal adapter contract for Codex CLI, Claude CLI, Cursor CLI, OpenCode/OpenClaw, and Copilot?
- Should Electron own Docker installation/updates, or only orchestrate an already-installed cell?
- Where should adapter health and run receipts live: API DB, `Agents/workframe`, or new cell manifest state?
- What is the least confusing UI copy that keeps Hermes visible as a trusted default without making it the product identity?

## Next best planning target

Environment/runtime detection map: exact probes, no-write guarantees, target manifest fields, and false-positive/false-negative risks for Hermes, Codex, Claude CLI, Cursor, OpenCode/OpenClaw, Copilot, Docker, GitHub, Vercel, provider keys, and OAuth sessions.
