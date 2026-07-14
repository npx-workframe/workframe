# Develop Workframe

Contributor path: edit source in this monorepo, then prove changes via a **generated dogfood install** (`npx create-workframe`).

## Dogfood (local)

```powershell
git clone https://github.com/npx-workframe/workframe.git
cd workframe
pnpm install
.\scripts\workframe\reset-dogfood-docker.ps1 -Confirm   # → ../MyBusiness
```

Open the UI URL printed by the script (typically `http://127.0.0.1:18644/`). Use `127.0.0.1`, not `localhost`.

**Release sign-off** (build + pack + reset): `.\scripts\workframe\sign-off-install.ps1`

DevOps map: [scripts/workframe/README.md](../../scripts/workframe/README.md)

## Monorepo layout

```text
apps/web/                      Product UI (Vite/React) — edit here
services/workframe-api/        API server (Python)
services/workframe-supervisor/ Secure-mode Docker exec broker
packages/create-workframe/     npx installer (publish mirror of built artifacts)
scripts/workframe.mjs          generated-project lifecycle helpers
infra/compose/workframe/       Reference compose template (not local dogfood)
scripts/workframe/             Ops scripts — see README.md
```

**Generated installs** (`npx create-workframe`) receive copies of API/UI/supervisor from the npm package. Product changes land here first, then sync into `packages/create-workframe/` before release.

## UI design system

Cosmetic / theme work: read [design.md](design.md) first, then the active theme doc ([Strato Dark](strato-dark-design.md), [Neo Light](neo-light-design.md), [Neo Blue](neo-blue-design.md)). Token lab: `pnpm dev:web` → `/dev/theme`.

## Generated install services (typical slot 1)

| Service | Port | Role |
|---------|------|------|
| workframe-ui | 18644 | Static SPA + nginx proxy |
| workframe-api | 19120 | API server |
| workframe-gateway | 18642 | Hermes native profile |
| workframe-dashboard | 19119 | Hermes dashboard proxy |
| workframe-supervisor | 18090 | Required when `SECURE_MODE=true` |

Ports come from the generated `.env` (`WORKFRAME_SLOT`).

## Security modes

Set in the **generated** install `.env` (wizard may persist to `stack_config.json`):

| Mode | Setting |
|------|---------|
| Production-style | `SECURE_MODE=true` (default in generated installs) |
| Local dev shortcut | `DEV_LOCAL_UNSAFE=true` — **never on a public URL** |

See [Security](./security.md).

## After code changes

```text
1. Edit apps/web/src/ and/or services/workframe-api/
2. pnpm build:web (if UI)
3. sync-canonical-to-package.mjs + bundle-workframe-ui.mjs (if API/UI)
4. sign-off-install.ps1  OR  in-app Admin → Updates on an existing install
```

Routine updates on a running install: **Admin → Updates** in the UI (not reset per change).

Details: [Release verification](./release.md)

## Scaffold smoke test (no dogfood reset)

```bash
node packages/create-workframe/scripts/test-scaffold.mjs
```

## Reference compose (advanced)

`infra/compose/workframe/` is a template only. See [infra/compose/workframe/README.md](../../infra/compose/workframe/README.md).

## Related

- [Contributing](./contributing.md)
- [Release verification](./release.md)
- [Install](./install.md) — end-user path
