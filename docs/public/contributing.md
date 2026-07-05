# Contributing

Thank you for considering a contribution to [Workframe](https://github.com/npx-workframe/workframe).

## Before you start

1. Read [What is Workframe?](./what-is-workframe.md) and [Develop](./develop.md)
2. Reset dogfood: `.\scripts\workframe\reset-dogfood-docker.ps1 -Confirm` (see [Develop](./develop.md))
3. For security findings, use [SECURITY.md](../../SECURITY.md) — not public issues

## How to contribute

### Bug reports

Open a [GitHub issue](https://github.com/npx-workframe/workframe/issues) with:

- What you expected vs what happened
- Deployment mode (`single_user_local`, `trusted_team`, `public_multi_user`)
- Steps to reproduce
- Relevant logs (redact secrets)

### Pull requests

1. Fork and branch from `main`
2. Make focused changes; match existing code style
3. Run local verification (below)
4. Open a PR with a clear description and test notes

We do not require a CLA. Contributions are under the project [LICENSE](../../LICENSE) (Apache-2.0).

## Local development

```powershell
git clone https://github.com/npx-workframe/workframe.git
cd workframe
pnpm install
.\scripts\workframe\reset-dogfood-docker.ps1 -Confirm
```

Full setup: [Develop](./develop.md)

## Where to work

| Area | Path |
|------|------|
| Product UI | `apps/web/src/` |
| API | `services/workframe-api/` |
| Supervisor | `services/workframe-supervisor/` |
| Installer | `packages/create-workframe/` |
| Reference compose template | `infra/compose/workframe/` (not local dogfood) |
| Ops scripts | `scripts/workframe/` |

UI or API changes that ship to end users must follow the canonical sync steps in [Release verification](./release.md) before npm publish.

## Verification before PR

Minimum for most changes:

```bash
pnpm test:ci
```

This runs public-repo verification, API `py_compile` typecheck, web build, UI bundle copy, and scaffold smoke tests for all packs.

For API, security, or installer changes, also run checks in [Release verification](./release.md).

## Documentation

Public docs live in `docs/public/`. Update docs when behavior changes. Verify against source (`server.py`, compose files, UI onboarding flow).

Sanitization rules for public docs: [MAINTAINER.md](../MAINTAINER.md)

## Code of conduct

Be respectful and constructive. Security issues deserve responsible disclosure via [SECURITY.md](../../SECURITY.md).

## Related

- [Release verification](./release.md) — pre-publish gate
- [Audit](./audit.md) — security review map
- [Operations](./operations.md) — running stacks
