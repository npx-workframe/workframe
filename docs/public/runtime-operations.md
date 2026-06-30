# Runtime operations

Reference stack: `infra/compose/workframe/docker-compose.yml`.

## Services

| Service | Default port | Role |
|---------|--------------|------|
| `workframe-ui` | 18644 | Web UI (nginx + static `apps/web/dist`) |
| `workframe-api` | 19120 | BFF |
| `workframe-gateway` | 18642 | Hermes native profile |
| `workframe-dashboard` | 19119 | Hermes dashboard proxy |
| `workframe-supervisor` | 18090 | Secure-mode Docker exec broker |

Open the UI at `http://127.0.0.1:18644` (use `127.0.0.1`, not `localhost`, for stable cookies).

## Security modes

Set in `infra/compose/workframe/.env`:

| Mode | Setting | Use |
|------|---------|-----|
| Production | `SECURE_MODE=true` | Default; supervisor holds Docker socket |
| Local dev only | `DEV_LOCAL_UNSAFE=true` | Never on a public URL |

Detail: [Security](./security.md).

## Supervisor (secure mode)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `POST` | `/v1/profile.start` | Start profile gateway |
| `POST` | `/v1/profile.stop` | Stop profile gateway |
| `POST` | `/v1/gateway.exec` | Hermes CLI in gateway container |
| `POST` | `/v1/hermes.user_exec` | Hermes CLI in user runtime home |

Requires `WORKFRAME_SUPERVISOR_TOKEN` in `.env`.

## Providers

- Admin configures OAuth app ids during install
- Each user connects LLM and integration keys via **Connect accounts**
- Agent chat and space @mentions require the acting user to have an LLM provider connected

## Chat surfaces

| Surface | Transport |
|---------|-----------|
| Agent DM | Hermes stream via BFF; per-user runtime profile |
| Human DM | SQLite messages |
| Space | SQLite + server-side @mention invoke; live SSE for agent turns |

Session binding: [Session architecture](./session-architecture.md).

## After code changes

```bash
pnpm build:web
docker compose -f infra/compose/workframe/docker-compose.yml restart workframe-api workframe-ui
```

Public deploy verification: `bash scripts/workframe/verify-public-deploy.sh`

Maintainer regression: [contributing.md](./contributing.md).
