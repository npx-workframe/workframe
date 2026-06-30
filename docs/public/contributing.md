# Contributing

For reviewers validating changes before release.

## Prerequisites

- Node ≥ 20, pnpm, Docker
- Python 3 for API `py_compile` typecheck in CI

## Build and run locally

```bash
pnpm install
pnpm build:web
cd infra/compose/workframe
cp .env.example .env
docker compose up -d --build
```

UI: `http://127.0.0.1:18644/`

## Scaffold smoke test

Generate a fresh project:

```bash
node packages/create-workframe/scripts/new-project.mjs SmokeDemo --out /tmp --force
```

Expected:

- `workframe-manifest.json`: `"pack": "native"`, one bootstrap profile `{slug}-agent`
- `docker-compose.yml`: exactly `gateway`, `dashboard`, `workframe-api`, `workframe` (no per-profile dashboard services)

Bootstrap after Hermes setup:

```bash
./Workframe/scripts/bootstrap-native.sh
```

Expected: `Agents/SOUL.md`, `Agents/profiles/{slug}-agent/SOUL.md`, `terminal.cwd` → `/workspace`.

## Runtime checks

```bash
docker compose up -d
npx workframe doctor
```

Expected: UI loads, `/hermes-dashboard/` loads, API health OK.

## Session routing

Via BFF:

- same profile + different `client_id` → different sessions
- same profile + same `client_id` → same persisted session

## Specialist lifecycle

```bash
node Workframe/scripts/agent-lifecycle.mjs create --slug qa-proof --display-name "QA Proof" --role "Smoke-test child"
node Workframe/scripts/agent-lifecycle.mjs delete --slug qa-proof
```

## CI checks

From the repository root:

```bash
pnpm install
pnpm test:ci
```

This runs public-repo verification, API `py_compile` typecheck, web build, UI bundle copy, and scaffold smoke tests for all packs.

## Public deploy preflight

```bash
bash scripts/workframe/verify-public-deploy.sh
```

See [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md) for multi-user VPS requirements.

## Scaffold regression

Covered by `pnpm test:ci` (or `node packages/create-workframe/scripts/test-scaffold.mjs` after `pnpm build:web` and bundling UI into the package).

Expected: passes for `native`, `core`, `product`, `engineering`, and `vanilla` packs.

## Canonical edit order (UI + API changes)

1. Edit `apps/web/src/` and/or `services/workframe-api/`
2. `pnpm build:web` if UI touched
3. `node packages/create-workframe/scripts/sync-canonical-to-package.mjs` if API/supervisor touched
4. `node packages/create-workframe/scripts/bundle-workframe-ui.mjs` if UI touched
5. Rebuild Docker API/supervisor images for dogfood if BFF changed

If docs disagree with code, code wins.
