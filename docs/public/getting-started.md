# Getting started

## For end users (generated project)

```bash
npx create-workframe@0.1.2 MyProject
cd MyProject
# Follow the install wizard, then open the Workframe UI URL shown at the end.
```

Generated layout:

```text
MyProject/
├── Agents/                 Hermes profiles and runtime state
├── Files/                  Project workspace (/workspace in containers)
├── scripts/                Bootstrap, lifecycle, `workframe.mjs` CLI
├── docker-compose.yml
├── workframe-api/
├── workframe-ui/
├── workframe-supervisor/
└── workframe-manifest.json
```

Project management (from generated project root):

```bash
node scripts/workframe.mjs doctor
node scripts/workframe.mjs setup
```

Or, if the `workframe` npm package is installed globally:

```bash
npx workframe doctor
npx workframe setup
```

## For contributors (this repository)

```bash
git clone https://github.com/npx-workframe/workframe.git
cd workframe
pnpm install
pnpm build:web
cd infra/compose/workframe
cp .env.example .env
docker compose up -d --build
```

Open the UI at `http://127.0.0.1:18644/` (use `127.0.0.1`, not `localhost`, for stable session cookies).

| Service | Host port | Role |
|---------|-----------|------|
| workframe-ui | 18644 | Static SPA |
| workframe-api | 19120 | BFF |
| workframe-gateway | 18642 | Hermes native profile |
| workframe-dashboard | 19119 | Hermes dashboard proxy |
| workframe-supervisor | 18090 | Required when `SECURE_MODE=true` |

Set security mode in `infra/compose/workframe/.env`:

- **Production-style:** `SECURE_MODE=true` (default when neither flag is set)
- **Local dev shortcut:** `DEV_LOCAL_UNSAFE=true` — never on a public URL

See [Runtime operations](./runtime-operations.md) and [Security](./security.md).

## Deployment modes

| Mode | Use case |
|------|----------|
| `single_user_local` | Solo machine, no email gate |
| `trusted_team` | Small trusted team on Docker/LAN |
| `public_multi_user` | HTTPS VPS with invite-only access |

Public deploy checklist: [infra/compose/workframe/PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md)

## License

Apache-2.0 — see [LICENSE](../../LICENSE), [SECURITY.md](../../SECURITY.md), [LICENSING.md](../LICENSING.md).
