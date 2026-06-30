# Contributing

For reviewers validating changes before release.

## Prerequisites

- Node ≥ 20, pnpm, Docker, Python 3 (for local API development)

## Build and run locally (monorepo)

```bash
git clone https://github.com/npx-workframe/workframe.git
cd workframe
pnpm install
pnpm build:web
cd infra/compose/workframe
cp .env.example .env
docker compose up -d --build
```

UI: `http://127.0.0.1:18644/`

Reference stack services: `gateway`, `dashboard`, `workframe-api`, `workframe-supervisor`, `workframe-ui`.

## Scaffold smoke test (monorepo)

Generate a scratch project without publishing:

```bash
node packages/create-workframe/scripts/new-project.mjs SmokeDemo --out /tmp --force
cd /tmp/SmokeDemo
```

Expected:

- `workframe-manifest.json`: `"pack": "native"`, one bootstrap profile `{slug}-agent`
- `docker-compose.yml`: five services — `gateway`, `dashboard`, `workframe-api`, `workframe-supervisor`, `workframe`

After Hermes setup in the generated project:

```bash
./scripts/bootstrap-native.sh
./scripts/verify-bootstrap.sh
```

Expected: `Agents/SOUL.md`, `Agents/profiles/{slug}-agent/SOUL.md`, `terminal.cwd` → `/workspace`.

## Runtime checks (generated project)

```bash
docker compose up -d
node scripts/workframe.mjs doctor
```

Expected: UI loads, `/hermes-dashboard/` loads, API health OK, native SOUL present.

## Session routing

Via BFF:

- same profile + different `client_id` → different sessions
- same profile + same `client_id` → same persisted session

## Specialist lifecycle

```bash
node scripts/agent-lifecycle.mjs create --slug qa-proof --display-name "QA Proof" --role "Smoke-test child"
node scripts/agent-lifecycle.mjs delete --slug qa-proof
```

## Monorepo regression scripts

From repository root:

```bash
node packages/create-workframe/scripts/test-scaffold.mjs
bash scripts/workframe/verify-public-deploy.sh
bash scripts/workframe/install-gate.sh   # or install-gate.ps1 on Windows
```

Expected: scaffold tests pass for `native`, `core`, `product`, `engineering`, and `vanilla` packs.

## Public deploy preflight

With a configured public overlay:

```bash
bash scripts/workframe/verify-public-deploy.sh
```

See [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md) for multi-user VPS requirements.

## Canonical edit order (UI + API changes)

1. Edit `apps/web/src/` and/or `services/workframe-api/`
2. `pnpm build:web` if UI touched
3. `node packages/create-workframe/scripts/sync-canonical-to-package.mjs` if API/supervisor touched
4. `node packages/create-workframe/scripts/bundle-workframe-ui.mjs` if UI touched
5. Rebuild Docker API/supervisor images for dogfood if BFF changed

If docs disagree with code, code wins.
