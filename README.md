# Workframe

**Repository:** [github.com/npx-workframe/workframe](https://github.com/npx-workframe/workframe)

**Install:** `npx create-workframe@0.1.18 MyProject`

Multi-user web shell around [Hermes Agent](https://github.com/NousResearch/hermes-agent) — UI, API, installer, and Docker Compose.

## New here?

| Goal | Start |
|------|--------|
| Learn what it is | [What is Workframe?](docs/public/what-is-workframe.md) |
| Install for your team | [Install guide](docs/public/install.md) |
| Review before deploy | [Audit guide](docs/public/audit.md) |
| Contribute code | [Develop](docs/public/develop.md) |

## Quick start (developers)

Edit source, then reset dogfood:

```powershell
.\scripts\workframe\reset-dogfood-docker.ps1 -Confirm   # npx create-workframe MyBusiness
```

DevOps map: [scripts/workframe/README.md](scripts/workframe/README.md)

Reference compose template (not local dogfood): `infra/compose/workframe/`

## End users

```bash
npx create-workframe@0.1.18 MyProject
```

## Layout

```text
apps/web                  Product UI (Vite/React)
services/workframe-api    API server
services/workframe-supervisor  Secure-mode exec broker
packages/create-workframe npm installer
packages/workframe        lifecycle CLI
infra/compose/workframe   Reference compose template (not local dogfood)
```

## Docs

Full index: [docs/README.md](docs/README.md)

## License

Apache-2.0 — [`LICENSE`](LICENSE), [`SECURITY.md`](SECURITY.md)
