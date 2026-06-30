# Operations

Day-to-day running of a Workframe stack: services, updates, backup, and common fixes.

Reference compose: `infra/compose/workframe/docker-compose.yml` (monorepo) or `docker-compose.yml` in a generated project.

## Services

| Service | Default port | Role |
|---------|--------------|------|
| `workframe-ui` | 18644 | Web UI (nginx + static assets) |
| `workframe-api` | 19120 | API server |
| `workframe-gateway` | 18642 | Hermes native profile |
| `workframe-dashboard` | 19119 | Hermes dashboard proxy |
| `workframe-supervisor` | 18090 | Secure-mode Docker exec broker |

Open the UI at `http://127.0.0.1:18644` (use `127.0.0.1`, not `localhost`, for stable cookies).

## Health check

```bash
curl -s http://127.0.0.1:19120/api/health | python3 -m json.tool
```

Check `deployment_mode`, `mode`, and component flags match your intent.

## Security modes

Set in `.env`:

| Mode | Setting | Use |
|------|---------|-----|
| Production | `SECURE_MODE=true` | Default; supervisor holds Docker socket |
| Local dev only | `DEV_LOCAL_UNSAFE=true` | Never on a public URL |

Detail: [Security](./security.md).

## Supervisor (secure mode)

When `SECURE_MODE=true`, profile lifecycle and gateway exec go through `workframe-supervisor` with `WORKFRAME_SUPERVISOR_TOKEN`.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `POST` | `/v1/profile.start` | Start profile gateway |
| `POST` | `/v1/profile.stop` | Stop profile gateway |
| `POST` | `/v1/gateway.exec` | Hermes CLI in gateway container |
| `POST` | `/v1/hermes.user_exec` | Hermes CLI in user runtime home |

## Providers and chat

- Admin configures OAuth app ids during install
- Each user connects LLM keys via **Connect accounts**
- Agent chat and space @mentions require the acting user to have an LLM provider connected

| Surface | Transport |
|---------|-----------|
| Agent DM | Hermes stream via API; per-user runtime profile |
| Human DM | SQLite messages |
| Space | SQLite + server-side @mention invoke; live SSE for agent turns |

Session binding: [Session architecture](./session-architecture.md).

## Updates

### Workframe (API, supervisor, UI)

Generated projects include `scripts/workframe/apply-update-workframe.sh`:

```bash
bash scripts/workframe/apply-update-workframe.sh
```

Preserves `Agents/`, `Files/`, `.env`, and API databases. Rebuilds API/supervisor containers. Optional npm template sync when `WORKFRAME_UPDATE_ALLOW_NPM=1` and `WORKFRAME_UPDATE_VERSION` are set.

Monorepo developers: pull git, `pnpm build:web`, rebuild/restart compose services — see [Develop](./develop.md).

### Hermes (gateway + dashboard images)

```bash
bash scripts/workframe/apply-update-hermes.sh
```

Pulls/recreates Hermes containers; preserves `Agents/` runtime state.

## Backup

Back up before major updates or VPS maintenance:

| Path | Contents |
|------|----------|
| `Agents/` | Hermes profiles, sessions, Kanban state |
| `Files/` | Project workspace |
| `workframe-api/data/` or `runtime/workframe-api-data/` | SQLite DBs, vault |
| `.env` | Secrets and mode configuration |

Restore: stop compose, restore directories and `.env`, `docker compose up -d --build`.

After suspected compromise, rotate `WORKFRAME_SUPERVISOR_TOKEN`, `WORKFRAME_API_TOKEN`, `WORKFRAME_PROXY_TOKEN`, and `ZK_AUTH_*` keys.

## Public deploy verification

```bash
bash scripts/workframe/verify-public-deploy.sh
```

See [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| UI **403** or empty page | Missing built UI (`apps/web/dist`) | `pnpm build:web` then restart `workframe-ui` |
| Session lost on refresh | `localhost` vs `127.0.0.1` | Use `http://127.0.0.1:<ui-port>` |
| API won't start (public mode) | Missing SMTP/secrets/HTTPS | Complete [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md) checklist |
| Agent chat errors | No user LLM key | Connect provider in user settings |
| `docker.sock` on API (public) | Wrong compose overlay | Use `docker-compose.public.yml` overlay |
| Install wizard stuck on email | SMTP misconfigured | Fix SMTP in wizard or use trusted local mode |

## After monorepo code changes

```bash
pnpm build:web
docker compose -f infra/compose/workframe/docker-compose.yml restart workframe-api workframe-ui
```

Release checks: [Release verification](./release.md)
