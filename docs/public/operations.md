# Operations

Day-to-day running of a Workframe stack: services, updates, backup, and common fixes.

## Dogfood reset (local)

```powershell
.\scripts\workframe\reset-dogfood-docker.ps1 -Confirm
```

Install path: `../MyBusiness` (sibling of the workframe repo). **Only** `npx create-workframe` — no manual bootstrap or compose from `infra/`.

DevOps map: [scripts/workframe/README.md](../../scripts/workframe/README.md)

## Stack layout

Generated install: `MyBusiness/docker-compose.yml` + `.env`  
Reference template (not dogfood): `infra/compose/workframe/docker-compose.yml`

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

SECURE_MODE stacks apply Workframe updates through **workframe-api → prefetch npm → workframe-supervisor → docker compose rebuild**. The API container has registry access; supervisor stays on the internal control network and never calls npm directly.

Generated projects include `scripts/workframe/apply-update-workframe.sh`:

```bash
bash scripts/workframe/apply-update-workframe.sh
```

Preserves `Agents/`, `Files/`, `.env`, and API databases. Rebuilds API/supervisor/UI containers. In-app apply sets `WORKFRAME_UPDATE_TARBALL` after the API downloads the pack; manual host runs may set `WORKFRAME_UPDATE_ALLOW_NPM=1` and `WORKFRAME_UPDATE_VERSION` instead.

After a successful apply, `workframe-api/data/package-version` and `workframe-manifest.json` record the installed pack version.

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

## Public deploy verification (VPS / reference compose)

Run against a **running public install** or reference compose with `.env` configured:

```bash
bash scripts/workframe/verify-public-deploy.sh /path/to/install-or-compose-dir
```

Not part of `install-gate` — dogfood sign-off is wizard + chat on a generated install.

See [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| UI **403** or empty page | Stale UI bundle in generated install | `pnpm build:web` + bundle + in-app Update, or reset |
| Session lost on refresh | `localhost` vs `127.0.0.1` | Use `http://127.0.0.1:<ui-port>` |
| API won't start (public mode) | Missing SMTP/secrets/HTTPS | Complete [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md) checklist |
| Agent chat errors | No user LLM key | Connect provider in user settings |
| `docker.sock` on API (public) | Wrong compose overlay | Use `docker-compose.public.yml` overlay |
| Corrupted dogfood / wizard stuck | Bad runtime state | `reset-dogfood-docker.ps1 -Confirm` |
| Install wizard stuck on email | SMTP misconfigured | Fix SMTP in wizard or use single_user_local mode |

Local dogfood is a **generated install** (`../MyBusiness`). Rebuild UI, sync installer, then use **Admin → Updates** on the running install — or `sign-off-install.ps1` for a full reset.

```powershell
pnpm build:web
node packages/create-workframe/scripts/sync-canonical-to-package.mjs   # if API touched
node packages/create-workframe/scripts/bundle-workframe-ui.mjs           # if UI touched
```

Release checks: [Release verification](./release.md)
