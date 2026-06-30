# API reference (shipped)

Workframe exposes a same-origin BFF at `/api/*` for the web UI. These endpoints are **internal to the product** — not a semver-stable public API.

For operators reviewing the implementation, primary handlers live in `services/workframe-api/server.py`.

## Auth and profile

| Method | Path | Purpose |
|--------|------|---------|
| `PATCH` | `/api/me` | Update user profile |
| `GET` | `/api/me/providers` | List connected providers |
| `POST` | `/api/me/credentials` | Store user credentials |
| `POST` | `/api/me/oauth/:id/start` | Start OAuth connect flow |

## Workspace and rooms

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/workspace/:id/members` | List members |
| `POST` | `/api/workspace/:id/invites` | Invite member |
| `DELETE` | `/api/workspace/:id/members` | Remove member |
| `GET` | `/api/rooms/:id/members` | Space members |
| `GET` | `/api/rooms/:id/messages` | Message history |
| `POST` | `/api/rooms/:id/messages/send` | Post message (supports @agent invoke) |
| `GET` | `/api/rooms/:id/live` | SSE live agent turns |
| `GET` | `/api/workspace/:wid/events` | Workspace revision SSE |

## Hermes profiles and chat

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/hermes/profiles/{profile}/bind` | Bind session for agent DM |
| `POST` | `/api/hermes/profiles/{profile}/messages/stream` | Stream chat |
| `GET` | `/api/hermes/models` | Model catalog (filtered by connected providers) |
| `POST` | `/api/hermes/model` | Set active model |
| `GET` | `/api/hermes/skills` | List skills |
| `GET` | `/api/hermes/commands` | Slash command catalog |
| `POST` | `/api/hermes/commands/exec` | Execute slash command |
| `POST` | `/api/hermes/profiles/create` | Create agent profile |
| `POST` | `/api/chat/stop` | Stop active agent run |
| `POST` | `/api/chat/steer` | Steer active agent run |

## Files

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/files/tree` | Workspace tree |
| `GET` | `/api/files/read` | Read file |
| `POST` | `/api/files/write` | Write file |
| `POST` | `/api/files/upload` | Upload file |

## Health and install

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/health` | Stack health and deployment mode |

Install-window endpoints (`/api/install/*`, `/api/auth/*`) gate first-run setup; see [Security](./security.md).

Hermes upstream: https://hermes-agent.nousresearch.com/docs/
