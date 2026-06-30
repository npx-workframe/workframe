# Architecture

Workframe is a multi-user shell around Hermes: web UI, auth, rooms, credential vault, and Docker compose packaging.

## Layers

```text
┌─────────────────────────────────────────────────────────┐
│  Workframe UI — chat, files, browser, activity         │
└───────────────────────────┬─────────────────────────────┘
                            │ /api/* (same origin)
┌───────────────────────────▼─────────────────────────────┐
│  workframe-api — auth, rooms, vault, chat proxy         │
└───────┬───────────────────────────────┬─────────────────┘
        │ HTTP + token (SECURE_MODE)     │ Hermes HTTP API
┌───────▼──────────┐            ┌────────▼────────────────┐
│ workframe-       │            │ workframe-gateway       │
│ supervisor       │            │ Hermes profiles         │
└──────────────────┘            └─────────────────────────┘
```

### Hermes

Agent runtime: profiles, sessions, skills, Kanban, gateway. Workframe does not fork or replace Hermes.

### Workframe API

Backend for the UI. Handles authentication, workspace/room state, file access, provider connect, session binding, and Hermes proxy routes.

### Workframe UI

Vite/React SPA. Nginx serves static assets and proxies `/api/*` and `/hermes-dashboard/*`.

### workframe-supervisor

When `SECURE_MODE=true`, holds the Docker socket; the API delegates profile lifecycle through a token-authenticated HTTP service. See [Security](./security.md).

## Source map (monorepo)

| Component | Repository path |
|-----------|-----------------|
| UI | `apps/web/src/` |
| API | `services/workframe-api/server.py` |
| Supervisor | `services/workframe-supervisor/server.py` |
| Reference compose | `infra/compose/workframe/` |
| Installer | `packages/create-workframe/` |

Generated installs receive built copies of API, UI, and supervisor from the npm package.

## Multi-user isolation

The Hermes gateway container mounts the shared `Agents/` tree. User isolation relies on per-user runtime profiles (`u-{user}-*`), role checks in the API, supervisor guards on sensitive profile paths, and encrypted credentials — not on disabling the terminal tool. See [Security](./security.md) and [Audit guide](./audit.md).

## Volumes (generated install)

| Host | Mount | Purpose |
|------|-------|---------|
| `Agents/` | `/opt/data` | Hermes profiles and state |
| `Files/` | `/workspace` | Project files (canonical truth) |

## Truth model

```text
Files  >  Kanban  >  Chat
```

Files hold durable project truth. Kanban tracks execution. Chat coordinates intent.

## Credentials

- **BYOK default** — each user connects providers in the UI
- **`user_only` providers** (GitHub, Vercel, Netlify) — no workspace fallback
- **Company-pays** — admin opt-in; stack keys on the native profile
- **Vault** — encrypted at rest; gateway uses per-turn lease tokens

## Where to read next

- [Using Workframe](./using-workframe.md) — product surfaces
- [Session architecture](./session-architecture.md) — chat binding
- [API reference](./api-reference.md) — HTTP routes used by the UI
- [Operations](./operations.md) — compose and day-to-day ops
- [PUBLIC_DEPLOY.md](../../infra/compose/workframe/PUBLIC_DEPLOY.md) — multi-user VPS
