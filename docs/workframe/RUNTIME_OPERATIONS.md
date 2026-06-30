# Workframe Runtime Operations (current)

**As of 2026-06-21** — source of truth: `services/workframe-api/server.py`, `services/workframe-supervisor/server.py`, `apps/web/`, `infra/compose/workframe/`.

## Stack (local Docker slot 1)

| Service | Role | Notes |
|---------|------|--------|
| `workframe-gateway` | Hermes native profile (`workframe-agent`) | `gateway run --replace`; port `18642` → container `8642` |
| `workframe-dashboard` | Nginx → Hermes dashboard | `19119` |
| `workframe-api` | Python BFF | `19120`; zk-auth, rooms, chat proxy, provider catalog |
| `workframe-supervisor` | Token-gated Docker exec | `18090`; **required when `SECURE_MODE=true`** |
| `workframe-ui` | Static UI (nginx) | `18644`; build with `pnpm build:web` |

Browser: `http://127.0.0.1:18644` (not `localhost` — session cookie stability).

## Security modes

Set **one** mode in `infra/compose/workframe/.env`:

| Mode | Env | Docker socket on API | Specialist gateway lifecycle |
|------|-----|----------------------|------------------------------|
| Production-style | `SECURE_MODE=true` | Blocked in Python (`_docker_request` raises) | Via `workframe-supervisor` HTTP + `WORKFRAME_SUPERVISOR_TOKEN` |
| Local dev shortcut | `DEV_LOCAL_UNSAFE=true` | API uses socket directly | `_gateway_exec` in API container |
| Default (neither set) | — | Same as secure | Same as secure |

Mutually exclusive: `SECURE_MODE=true` + `DEV_LOCAL_UNSAFE=true` → process refuses to start.

See also: `secure-mode-design.md`, `supervisor-design.md`.

## workframe-supervisor

Security boundary, not a product feature. Holds `/var/run/docker.sock`; API calls it over HTTP with bearer token.

**Implemented endpoints** (`services/workframe-supervisor/server.py`):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Unauthenticated health |
| `GET` | `/v1/profile.status?profile=` | Gateway state for one profile |
| `GET` | `/v1/stack.status` | All routed profiles |
| `POST` | `/v1/profile.start` | `hermes -p <profile> gateway start` (+ config patch) |
| `POST` | `/v1/profile.stop` | Gateway stop |
| `POST` | `/v1/profile.disable` | Stop + disable platforms in `config.yaml` |
| `POST` | `/v1/gateway.exec` | Arbitrary `hermes -p <profile> …` in gateway container |
| `POST` | `/v1/hermes.user_exec` | `hermes …` in a user Hermes home (`/opt/data/profiles/{user_slug}`) |

When `SECURE_MODE=true`, `workframe-api` routes `_gateway_exec` and `_hermes_user_exec` through the supervisor instead of the socket.

Token: `WORKFRAME_SUPERVISOR_TOKEN` in `.env` (generate: `scripts/workframe/setup-supervisor.sh` or `openssl rand -hex 32`).

## Profile API lifecycle (`ensure_profile_api`)

Specialist profiles (e.g. `architect`) expose an HTTP API on a stable port inside `workframe-gateway` (`http://gateway:<port>/…` from the API container).

**Current behavior (2026-06-20):**

1. `_bootstrap_profile_providers` — seed specialist `auth.json` / user `.env` sync (no stack keys for normal users; owner/admin can use stack fallback).
2. If health check passes → return immediately (**no gateway stop/restart**).
3. If down → start via `profile_gateway_lifecycle` (supervisor in secure mode), wait for health, then return.

**Removed:** reloading a healthy gateway on every bootstrap/env change (caused `Connection refused` races during space `@mentions` and agent chat).

Per-turn payer keys: `_overlay_turn_provider_env` writes the triggering user's LLM secret into the specialist `.env` before each chat turn (ponytail: concurrent users on same profile can race).

## Provider connect & model picker

**Policy (2026-06-21):** security-first deny-by-default. Workspace admin configures OAuth app ids/secrets (e.g. GitHub); each user connects their own OAuth or API tokens. `user_only` providers (GitHub, Vercel, Netlify) resolve via `_resolve_credential(..., user_only=True)` — **no workspace credential fallback**.

**Catalog:** `PROVIDER_CONNECT_CATALOG` in `server.py` — Hermes-native env vars + OAuth ids (OpenRouter, Anthropic, OpenAI, Gemini, DeepSeek, Brave, Codex OAuth, Discord/Telegram/Slack bots, GitHub/Vercel/Netlify dev).

**UI:** Profile sheet → **Connect accounts** (`ProviderConnectPanel.tsx`). Keys land in user Hermes home: `Agents/profiles/{user_slug}/.env`.

**Visibility:**

- `GET /api/me/providers` — `connected`, `source` (`user` | `stack`), `stack_managed` for owner/admin.
- `GET /api/hermes/models` — `has_llm_provider`, `connected_providers`; suggestions filtered to connected LLM providers only.

**Gating:** Agent chat and space `@mentions` require the triggering user to have an LLM provider (`no_llm_provider_for_user`). UI shows **Connect provider** CTA on errors (`WorkframeNotice` + model switcher inactive state).

## Chat surfaces

| Surface | Storage / transport | Hermes profile | Session |
|---------|---------------------|----------------|---------|
| Agent DM | Browser Hermes SSE via BFF | Per-user runtime `u-{user}-{agent}` | `profile_chat_bind` + `room_id` |
| Human DM | SQLite `messages` | — | Room membership |
| Space (e.g. General) | SQLite `messages` + server stream fanout | Template agent slug | `room_sessions`; `source_id=room`, `client_id=room_id` |

### Space `@mentions`

1. `POST /api/rooms/:id/messages/send` → insert user message (`invoke_agents` defaults `true`; set `false` only to suppress server invoke).
2. `_process_space_message_mentions` — match `@slug` or display name → `_invoke_room_agent_mention` (thread).
3. Thread: `profile_chat_session` (room-scoped) → `_profile_turn_payload(..., room_id)` (transcript in prompt) → overlay payer env → Hermes `…/chat/stream`.
4. **Room live SSE** (`GET /api/rooms/:id/live`): `turn.started` / `turn.update` (segments, ~50ms coalesce) / `turn.complete` — all room members see the same live turn.
5. Final reply inserted as `sender_agent_id`; workspace SSE revision bumps for persisted history reload.

Agent posts via send API use `sender_agent_id` only (no `sender_user_id`); BFF validates agent is a room member.

**Message list:** `GET /api/rooms/:id/messages` returns the **latest N** messages (subquery `ORDER BY created_at DESC LIMIT N`, re-sorted ASC) — not the oldest N.

See `SESSION_FLOW.md` for agent DM / lane registry detail.

## Frontend refresh (spaces)

- `watchRoomLive` — `GET /api/rooms/:id/live` SSE; live agent turns merged into message list (`roomLive.ts`, rAF batching).
- `watchWorkspaceEvents` — workspace SSE; **ignores `heartbeat` frames** (15s keepalive); debounced silent reload of persisted messages (~450ms).
- `ChatSplit` — optimistic user send; no client-side Hermes stream for space `@mentions`.
- `AgentRailPanel` — debounced workspace reload on revision change.

**Deploy note:** UI serves `apps/web/dist`. After API restart, restart `workframe-ui` if nginx cached a stale API container IP (see `apps/web/docker/nginx.conf` Docker DNS resolver).

## Tests

```bash
cd services/workframe-api
python -m pytest tests/test_provider_bootstrap.py tests/test_supervisor_lifecycle.py tests/test_ensure_profile_api.py tests/test_room_tenancy.py -q
```

```bash
# from repository root
pnpm build:web
docker compose -f infra/compose/workframe/docker-compose.yml restart workframe-api workframe-ui
```

## Agent adapters (planned — not in code yet)

Workframe is adding a **runtime seam** so agents can run on native `compose_hermes` (today's default) or external **NemoHermes** without changing chat UI or vault semantics. Design only as of 2026-06-26.

| Doc | Purpose |
|-----|---------|
| [adapters-overview.md](./adapters-overview.md) | Why adapters; two-step plan |
| [adapter-step1-runtime-seam.md](./adapter-step1-runtime-seam.md) | `runtime_kind`, resolver, Stripe, NemoHermes stub |
| [adapter-external-references.md](./adapter-external-references.md) | Hermes + NemoClaw official docs |

Until `runtime_kind` ships, all profiles use hardcoded `http://gateway:{port}` (see `_profile_api_port`).

## Related docs

- `hermes-bff-route-map.md` — UI → BFF matrix
- `SESSION_FLOW.md` — agent session / lane registry
- `supervisor-design.md` — supervisor design + migration notes
- `secure-mode-design.md` — SECURE_MODE / DEV_LOCAL_UNSAFE
- `adapters-overview.md` — agent adapter program (planned)
