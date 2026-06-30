# Architecture

Source of truth: `services/workframe-api/server.py`, `services/workframe-supervisor/server.py`, `apps/web/src/`, `infra/compose/workframe/`.

## Layers

```text
┌─────────────────────────────────────────────────────────┐
│  Workframe UI (apps/web) — chat, files, browser, activity │
└───────────────────────────┬─────────────────────────────┘
                            │ /api/* (same origin)
┌───────────────────────────▼─────────────────────────────┐
│  workframe-api (BFF) — auth, rooms, vault, chat proxy    │
└───────┬───────────────────────────────┬─────────────────┘
        │ HTTP + token (SECURE_MODE)     │ Hermes HTTP API
┌───────▼──────────┐            ┌────────▼────────────────┐
│ workframe-       │  docker    │ workframe-gateway       │
│ supervisor       │  exec      │ Hermes profiles + gateway│
└──────────────────┘            └─────────────────────────┘
```

### Hermes (engine)

Provides profiles, sessions, memory, skills, Kanban, and gateway APIs. Workframe does not replace Hermes internals.

### Workframe API (BFF)

Internal UI backend — **not** a stable public API contract. Responsibilities include:

- Route and lane discovery
- Profile lifecycle and runtime profile provisioning
- Session binding (`room_sessions`, lane registry cache)
- File tree access to `/workspace`
- Provider connect catalog and credential vault
- Room/space chat, SSE fanout, activity aggregation

### Workframe UI

Vite/React SPA served by nginx. Proxies `/api/*` and `/hermes-dashboard/*` to backend services.

### workframe-supervisor

Security boundary when `SECURE_MODE=true`. Holds the Docker socket; the BFF calls it over HTTP with `WORKFRAME_SUPERVISOR_TOKEN`. See [Security](./security.md).

## Volume model (generated install)

| Host path | Container mount | Purpose |
|-----------|-----------------|---------|
| `Agents/` | `/opt/data` | Hermes profiles, state.db, kanban.db |
| `Files/` | `/workspace` | User project files (canonical truth) |

## Session model (summary)

| Store | Owns |
|-------|------|
| `workframe.db` → `room_sessions` | Active Hermes `session_id` per `(room_id, agent_profile_id)` |
| Hermes `state.db` | Message rows per profile/session |
| `lane-registry.json` | Derived cache for UI tab hints — not authoritative when `room_id` is set |

Full detail: [Session architecture](./session-architecture.md).

## Credential model

- **Default:** BYOK — each user connects OAuth or API keys via the UI
- **`user_only` providers** (GitHub, Vercel, Netlify): no workspace fallback
- **Company-pays:** explicit admin opt-in; stack keys on primary profile `.env`
- **Vault:** envelope-encrypted secrets in API data dir; per-turn lease tokens for gateway proxy

## Deployment surfaces

| Surface | Path |
|---------|------|
| Reference compose | `infra/compose/workframe/` |
| Installer | `packages/create-workframe/` → npm `create-workframe` |
| VPS notes | `infra/vps/README.md` |
| Public multi-user | `infra/compose/workframe/PUBLIC_DEPLOY.md` |

## UI ↔ BFF coverage

See [BFF route map](./bff-route-map.md) for endpoint-level status (real, deferred, planned).

## Runtime note

All agent chat today routes through the shared `workframe-gateway` container (`compose_hermes`). External runtime adapters are not merged in core yet; profiles resolve via `_profile_api_port` to `http://gateway:{port}`.
