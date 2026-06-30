# Workframe

**Repository:** [github.com/npx-workframe/workframe](https://github.com/npx-workframe/workframe)

**Install:** `npx create-workframe@0.1.3 MyProject`

Multi-user web shell around [Hermes Agent](https://github.com/NousResearch/hermes-agent) — UI, API, installer, and Docker Compose.

## New here?

| Goal | Start |
|------|--------|
| Learn what it is | [What is Workframe?](docs/public/what-is-workframe.md) |
| Install for your team | [Install guide](docs/public/install.md) |
| Review before deploy | [Audit guide](docs/public/audit.md) |
| Contribute code | [Develop](docs/public/develop.md) |

## Quick start (developers)

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
npx create-workframe@0.1.3 MyProject
```

## Layout

```text
apps/web                  Product UI (Vite/React)
services/workframe-api    API server
services/workframe-supervisor  Secure-mode exec broker
packages/create-workframe npm installer
packages/workframe        lifecycle CLI
infra/compose/workframe   Docker stack
```

## Docs

Full index: [docs/README.md](docs/README.md)

## License

Apache-2.0 — [`LICENSE`](LICENSE), [`SECURITY.md`](SECURITY.md)
