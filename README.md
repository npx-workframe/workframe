# Workframe

**Repository:** [github.com/npx-workframe/workframe](https://github.com/npx-workframe/workframe)

**Install:** `npx create-workframe@0.1.1 MyProject`

Monorepo for Workframe — UI, API, installer, and Docker compose.

## Layout

```text
apps/web                  Product UI (Vite/React)
services/workframe-api    Python BFF
services/workframe-supervisor  Secure-mode exec broker
packages/create-workframe npm installer
packages/workframe        lifecycle CLI
infra/compose/workframe   Docker stack
```

## Quick start

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

## End users

```bash
npx create-workframe@0.1.1 MyProject
```

## Docs

[`docs/README.md`](docs/README.md) · [`docs/workframe/RUNTIME_OPERATIONS.md`](docs/workframe/RUNTIME_OPERATIONS.md)

## License

Apache-2.0 — [`LICENSE`](LICENSE), [`SECURITY.md`](SECURITY.md)
