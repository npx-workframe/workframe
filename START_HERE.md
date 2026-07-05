# Workframe — agent entry

**You are in the product source repo.** Read this before editing code or running sandboxes.

Chain of truth: **source here** → ABKB curated memory → chat hints.

## What this repo is

| Concept | Path / name |
|---------|-------------|
| **Product** | `create-workframe` npm pack (`npx create-workframe`) |
| **Source** | This repo — `github.com/npx-workframe/workframe` |
| **Method** | Hermes-backed collaboration layer (not a Hermes fork) |

## Cascade (read in order)

```text
1. This file (START_HERE.md)
2. AGENTS.md — mutation discipline, harness pointer
3. ABKB projects/workframe/project_profile.md — ontology + risks
4. ABKB projects/workframe/install-sandbox-doctrine.md — sign-off spine
5. .harness/feature_list.json — scenario ledger (what must pass)
6. docs/public/architecture.md — vault, supervisor, layers
7. docs/public/security.md — SECURE_MODE, leases, BYOK
8. docs/public/session-architecture.md — u-{user}-* profiles, binding
9. Source grep — then smallest edit
```

**Cursor release loop:** `d:/ab/.cursor/skills/workframe-release/SKILL.md`  
**Environment map:** `d:/ab/.cursor/rules/workframe-environments.mdc`

## Four targets (never confuse)

| Target | What | Edit product code? |
|--------|------|-------------------|
| **Source** | This repo | **Yes** — `services/workframe-api/`, `apps/web/src/` |
| **Dogfood local** | `../MyBusiness` from `npx create-workframe` → `http://127.0.0.1:<ui-port>/` | **No** — reset only |
| **Dogfood VPS** | `/opt/workframe/MyBusiness` from pack/`npx` | **Never** scp hotfix |
| **Host Hermes** | `%LOCALAPPDATA%\hermes` | **OFF LIMITS** — personal AIbert |

**Local dogfood reset:** `.\scripts\workframe\reset-dogfood-docker.ps1 -Confirm`  
**Release sign-off:** `.\scripts\workframe\sign-off-install.ps1`  
**DevOps map:** `scripts/workframe/README.md`

`infra/compose/workframe/` is a **reference compose template** (synced to the installer), not the local dogfood runtime.

Workframe Hermes = Docker gateway in the generated install. Never run host `hermes.exe`.

## Slots (local installs — `create-workframe` allocates)

| Slot | UI | API | Typical use |
|------|-----|-----|-------------|
| 1 | `18644` | `19120` | Local `MyBusiness` (default when free) |
| 2 | `28644` | `29120` | VPS `MyBusiness` |
| 3 | `38644` | `39120` | E2E unsafe (`WORKFRAME_E2E_UNSAFE=1`) |

Use `http://127.0.0.1` not `localhost` for session cookies.

## Canonical edit order (mandatory)

```text
services/workframe-api/ | apps/web/src/
  → pnpm build:web (if UI)
  → node packages/create-workframe/scripts/sync-canonical-to-package.mjs
  → node packages/create-workframe/scripts/bundle-workframe-ui.mjs (if UI)
  → rebuild generated install via in-app Update after publish (not infra/compose up)
```

**Never backwards:** editing `packages/create-workframe/workframe-api/` or `workframe-ui/public/` alone leaves sandboxes behind.

## Ledger (this repo)

| File | Purpose |
|------|---------|
| `.harness/feature_list.json` | Scenario pass/fail — product operator ledger |
| `.harness/verify.mjs` | Cloud verify runner (`HARNESS_CHECK=1` in CI) |
| `operations/log.md` | Append-only operator log (this repo) |
| ABKB `operations/daily/.../work_items` | PM → worker assignment queue (cross-repo) |

Run: `node .harness/verify.mjs` or `pnpm test:ci`.

**Known failing scenarios (2026-07-04):** `installer-ui-bundle` (local), `dogfood-install-gate` (run `sign-off-install.ps1` + wizard).

## Policies enforced (pitfalls)

| Topic | Rule |
|-------|------|
| **Installer vs source** | Source first; sync to package; bundle UI for parity |
| **Sign-off** | `sign-off-install.ps1` → wizard → chat — green CI alone is **not** sign-off |
| **Routine updates** | In-app Admin → Updates — not wipe per change |
| **SECURE_MODE** | Supervisor brokers Hermes lifecycle — API has no Docker socket |
| **Vault** | `WORKFRAME_API_DATA_DIR`; credentials in API vault |
| **Key lease** | `wf_rt_*` in profile `.env`; LLM via `/internal/llm/` proxy |
| **Runtime profiles** | `u-{user}-{agent}` for DMs; selection-only picker before profile exists |
| **s6** | Gateway process management in container (`register-gateways.sh`) — not the same as workframe-supervisor |
| **supervisor** | `services/workframe-supervisor/` — profile exec broker when `SECURE_MODE=true` |
| **Company-pays vs BYOK** | Default BYOK; admin opt-in; `user_only` providers never fall back to workspace creds |

Full doctrine: ABKB `projects/workframe/install-sandbox-doctrine.md`.

## Role rail (automations)

When running as a **role** (not ad-hoc chat):

1. Load `abkb/operations/roles/<role-id>/` (identity + prompt)
2. Return here for project map
3. One task per run; update ledger + `work_items` when done

PM-workframe enqueues workers in ABKB `queues.json`. Coder workers implement here and open PR.

## Docs index

- `docs/README.md` — public vs private vs archive
- `docs/public/develop.md` — contributor dev
- `docs/public/release.md` — install-gate, CI
- `docs/public/operations.md` — troubleshooting

Private operator detail: ABKB `projects/workframe/internal/` (not in public clone).
