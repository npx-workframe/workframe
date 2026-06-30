# Develop Workframe

Contributor path: clone the monorepo, build the UI, run the reference Docker stack.

```bash
git clone https://github.com/npx-workframe/workframe.git
cd workframe
pnpm install
pnpm build:web
cd infra/compose/workframe
cp .env.example .env
docker compose up -d --build
```

UI: `http://127.0.0.1:18644/` (use `127.0.0.1`, not `localhost`)

## Monorepo layout

```text
apps/web/                      Product UI (Vite/React) — edit here
services/workframe-api/        API server (Python)
services/workframe-supervisor/ Secure-mode Docker exec broker
packages/create-workframe/     npx installer (copies built artifacts into generated projects)
packages/workframe/            lifecycle CLI
infra/compose/workframe/       Reference Docker stack
scripts/workframe/             Ops and verification scripts
```

**Generated installs** (`npx create-workframe`) receive copies of API/UI/supervisor from the npm package. Product changes land in this monorepo first, then sync into `packages/create-workframe/` before release.

## Reference stack services

| Service | Port | Role |
|---------|------|------|
| workframe-ui | 18644 | Static SPA + nginx proxy |
| workframe-api | 19120 | API server |
| workframe-gateway | 18642 | Hermes native profile |
| workframe-dashboard | 19119 | Hermes dashboard proxy |
| workframe-supervisor | 18090 | Required when `SECURE_MODE=true` |

## Local security modes

In `infra/compose/workframe/.env`:

| Mode | Setting |
|------|---------|
| Production-style | `SECURE_MODE=true` (default) |
| Local dev shortcut | `DEV_LOCAL_UNSAFE=true` — **never on a public URL** |

See [Security](./security.md).

## After code changes

```bash
pnpm build:web
docker compose -f infra/compose/workframe/docker-compose.yml restart workframe-api workframe-ui
```

If API or supervisor code changed, rebuild images:

```bash
docker compose -f infra/compose/workframe/docker-compose.yml build workframe-api workframe-supervisor
docker compose -f infra/compose/workframe/docker-compose.yml up -d workframe-api workframe-supervisor
```

## Canonical edit order (UI + API)

Before release or installer pack:

1. Edit `apps/web/src/` and/or `services/workframe-api/`
2. `pnpm build:web` if UI touched
3. `node packages/create-workframe/scripts/sync-canonical-to-package.mjs` if API/supervisor touched
4. `node packages/create-workframe/scripts/bundle-workframe-ui.mjs` if UI touched
5. Rebuild Docker API/supervisor images locally to verify

Details: [Release verification](./release.md)

## Scaffold smoke test

Generate a scratch project without publishing:

```bash
node packages/create-workframe/scripts/new-project.mjs SmokeDemo --out /tmp --force
cd /tmp/SmokeDemo
docker compose up -d
node scripts/workframe.mjs doctor
```

## Related

- [Contributing](./contributing.md) — issues, PRs, expectations
- [Release verification](./release.md) — regression scripts before publish
- [Audit](./audit.md) — security review map
- [Install](./install.md) — end-user path (different audience)
