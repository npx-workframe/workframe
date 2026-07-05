# Workframe DevOps — operator map

**Dogfood = generated Docker install via `create-workframe`. Period.**

No manual bootstrap scripts, no copying SMTP/OAuth into compose `.env`, no `infra/compose/workframe` + `runtime/` as the local dogfood runtime.

| Surface | Install path | Reset command |
|---------|--------------|---------------|
| **Local dogfood** | `../MyBusiness` (sibling of this repo under `projects/`) | `.\reset-dogfood-docker.ps1 -Confirm` |
| **VPS dogfood** | `/opt/workframe/MyBusiness` | `bash reset-vps-runtime.sh [pack.tgz]` |
| **Source** | This repo — edit `services/`, `apps/web/src/` only | — |
| **Host Hermes** | `%LOCALAPPDATA%\hermes` | **OFF LIMITS** |

After reset: open the printed UI URL → complete the **wizard in the browser**. Either it boots or it doesn't.

---

## Primary commands

| Goal | Command |
|------|---------|
| **Reset local dogfood** | `.\scripts\workframe\reset-dogfood-docker.ps1 -Confirm` |
| **Preview reset** | `.\scripts\workframe\reset-dogfood-docker.ps1 -WhatIf` |
| **Release sign-off** (build + pack + reset) | `.\scripts\workframe\sign-off-install.ps1` |
| **Pre-publish gate** (no install) | `.\scripts\workframe\install-gate.ps1` |
| **Reset VPS sandbox** | `.\scripts\workframe\reset-vps-runtime.ps1 -VpsHost user@host` |
| **VPS tunnel** | `.\scripts\workframe\open-vps-tunnel.ps1` |
| **Publish npm** | `.\scripts\workframe\publish-npm.ps1` |

---

## Release loop (source → npm → dogfood)

```text
1. Edit services/workframe-api/ | apps/web/src/
2. pnpm build:web  (if UI)
3. sync-canonical-to-package.mjs + bundle-workframe-ui.mjs  (if API/UI)
4. sign-off-install.ps1   OR   install-gate.ps1 then reset-dogfood-docker.ps1 -Confirm
5. Wizard + chat in browser
6. publish-npm.ps1
7. Routine updates: in-app Admin → Updates (not reset per change)
```

Full skill: `d:/ab/.cursor/skills/workframe-release/SKILL.md`

---

## Port slots (`create-workframe` auto-picks first free)

| Slot | UI | API | Typical use |
|------|-----|-----|-------------|
| 1 | 18644 | 19120 | Local `MyBusiness` (default when free) |
| 2 | 28644 | 29120 | VPS `MyBusiness` |
| 3 | 38644 | 39120 | E2E unsafe (`WORKFRAME_E2E_UNSAFE=1`) |
| 4+ | 48xxx | 49xxx | Extra disposable installs |

Use `http://127.0.0.1` not `localhost` for cookies.

---

## What `infra/compose/workframe/` is now

**Reference compose only** — template synced into `create-workframe`, documented in `docs/public/develop.md`.  
It is **not** the local dogfood runtime. Do not `docker compose up` there for product sign-off.

---

## Deprecated (do not use)

| Script | Use instead |
|--------|-------------|
| `fresh-local-install.ps1` | `reset-dogfood-docker.ps1 -Confirm` |
| `run-local-pack-install.ps1` | `sign-off-install.ps1` |
| `reset-vps-runtime.sh` (old bootstrap path) | new `reset-vps-runtime.sh` in this folder |
| `vps-pack-install-remote.sh` (manual bootstrap) | `reset-vps-runtime.sh` with pack arg |
| `wipe-vps-docker.sh` | `reset-vps-runtime.sh` |
| `doctor-repair.mjs` (compose dogfood) | `reset-dogfood-docker.ps1 -Confirm` |
| `repair-dogfood-memberships.ps1` | reset + wizard |
| `restore-docker-runtime-from-meta.ps1` | reset |
| `run-dogfood-install-e2e.ps1` (no Playwright spec) | reset + manual wizard |
| `e2e-slot3-up.ps1` | Playwright CI only — not dogfood |

Optional post-wizard API smoke (not sign-off): `scripts/workframe/journey-test.py` with `OPENROUTER_API_KEY` set.


## Generated install layout (`MyBusiness/`)

```text
MyBusiness/
├── Agents/          Hermes runtime (disposable)
├── Files/           Workspace
├── docker-compose.yml
├── workframe-api/   from npm pack
├── workframe-ui/
└── .env             install identity (gitignored)
```

---

## CI / harness

- Cloud: `node .harness/verify.mjs` (`pnpm test:ci`)
- Local sign-off: `sign-off-install.ps1` then manual wizard + chat
- Scenario ledger: `.harness/feature_list.json`
