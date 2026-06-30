# Runtime operations

Grounded in `services/workframe-api/server.py`, `services/workframe-supervisor/server.py`, `apps/web/`, and `infra/compose/workframe/`.

## Compose services (reference stack)

| Service | Role | Notes |
|---------|------|--------|
| `workframe-gateway` | Hermes native profile | `gateway run --replace`; host `18642` → container `8642` |
| `workframe-dashboard` | Nginx → Hermes dashboard | `19119` |
| `workframe-api` | Python BFF | `19120`; auth, rooms, chat proxy, provider catalog |
| `workframe-supervisor` | Token-gated Docker exec | `18090`; **required when `SECURE_MODE=true`** |
| `workframe-ui` | Static UI (nginx) | `18644`; build with `pnpm build:web` |

Browser: `http://127.0.0.1:18644` (prefer `127.0.0.1` over `localhost` for cookie stability).

## Security modes

Set in `infra/compose/workframe/.env`:

| Mode | Env | Docker socket on API | Specialist gateway lifecycle |
|------|-----|----------------------|------------------------------|
| Production-style | `SECURE_MODE=true` | Blocked (`_docker_request` raises) | Via supervisor HTTP + token |
| Local dev shortcut | `DEV_LOCAL_UNSAFE=true` | API uses socket directly | `_gateway_exec` in API container |
| Default (neither set) | — | Same as secure | Same as secure |

Mutually exclusive: `SECURE_MODE=true` + `DEV_LOCAL_UNSAFE=true` → process refuses to start.

Detail: [Security](./security.md).

## Supervisor endpoints

Implemented in `services/workframe-supervisor/server.py`:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Unauthenticated health |
| `GET` | `/v1/profile.status?profile=` | Gateway state for one profile |
| `GET` | `/v1/stack.status` | All routed profiles |
| `POST` | `/v1/profile.start` | Start gateway for profile |
| `POST` | `/v1/profile.stop` | Stop gateway |
| `POST` | `/v1/profile.disable` | Stop + disable platforms in config |
| `POST` | `/v1/gateway.exec` | Hermes CLI in gateway container |
| `POST` | `/v1/hermes.user_exec` | Hermes CLI in user runtime home |

Token: `WORKFRAME_SUPERVISOR_TOKEN` in `.env`.

## Profile API lifecycle

Specialist profiles expose HTTP on a port inside `workframe-gateway`.

Current behavior:

1. `_bootstrap_profile_providers` — seed specialist auth; sync user `.env`
2. If health check passes → return immediately (no gateway restart)
3. If down → start via supervisor (secure mode), wait for health

Per-turn payer keys: `_overlay_turn_provider_env` writes the triggering user's LLM secret into the specialist `.env` before each chat turn. Concurrent users on the same shared specialist profile can race — known ceiling.

## Provider connect

Policy: deny-by-default. Admin configures OAuth app ids; each user connects their own tokens.

- Catalog: `PROVIDER_CONNECT_CATALOG` in `server.py`
- UI: Profile sheet → **Connect accounts** (`ProviderConnectPanel.tsx`)
- Keys land in `Agents/profiles/{user_slug}/.env`
- `user_only` providers: `_resolve_credential(..., user_only=True)` — no workspace fallback

Gating: agent chat and space `@mentions` require the triggering user to have an LLM provider.

## Chat surfaces

| Surface | Storage | Hermes profile | Session |
|---------|---------|----------------|---------|
| Agent DM | BFF → Hermes SSE | `u-{user}-{agent}` | `profile_chat_bind` + `room_id` |
| Human DM | SQLite `messages` | — | Room membership |
| Space | SQLite + server stream | Template agent slug | `room_sessions` |

### Space `@mentions`

1. `POST /api/rooms/:id/messages/send` inserts user message
2. `_process_space_message_mentions` → `_invoke_room_agent_mention`
3. Room-scoped Hermes stream with payer env overlay
4. `GET /api/rooms/:id/live` SSE: `turn.started` / `turn.update` / `turn.complete`
5. Final reply persisted; workspace SSE bumps revision

Agent DM session detail: [Session architecture](./session-architecture.md).

## Frontend refresh

- `watchRoomLive` — room SSE for live agent turns
- `watchWorkspaceEvents` — workspace SSE (ignores heartbeat keepalives)
- UI serves `apps/web/dist` — rebuild after UI changes; restart `workframe-ui` if nginx cached stale API IP

## Verification commands

```bash
cd services/workframe-api
python -m pytest tests/test_provider_bootstrap.py tests/test_supervisor_lifecycle.py tests/test_ensure_profile_api.py tests/test_room_tenancy.py -q
```

```bash
pnpm build:web
docker compose -f infra/compose/workframe/docker-compose.yml restart workframe-api workframe-ui
```

Public deploy preflight: `bash scripts/workframe/verify-public-deploy.sh`

## Related

- [BFF route map](./bff-route-map.md)
- [Security](./security.md)
- [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md)
