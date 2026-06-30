# Workframe UI (`apps/web`)

Product shell SPA — chat, files, browser, activity. Built to `dist/` and served by nginx in the `{slug}-workframe` compose service.

Docs: [docs/public/architecture.md](../../docs/public/architecture.md), [docs/public/api-reference.md](../../docs/public/api-reference.md)

## Stack

Vite · React · TypeScript · Dockview · shadcn/ui · Tailwind · Lucide

## Scripts (from repository root)

| Command | Purpose |
|---------|---------|
| `pnpm --filter @workframe/web dev` | Vite dev server (HMR) |
| `pnpm build:web` | Production build → `apps/web/dist` |

Local dogfood mounts `apps/web/dist` in `infra/compose/workframe`.

## Runtime wiring

Nginx serves the SPA and proxies:

- `/api/*` → `workframe-api`
- `/hermes-dashboard/*` → Hermes dashboard (WebSockets)

Dev server (`vite.config.ts`) mirrors the same routes.

Primary data paths:

- `/api/meta`, `/api/agents`, `/api/routes`
- `/api/hermes/profiles/{profile}/bind|messages|messages/stream`
- `/api/files/*`, `/api/rooms/*`
- Room live SSE: `/api/rooms/:id/live`

Session binding: `profile + source_id + client_id`. See [session architecture](../../docs/public/session-architecture.md).

## Structure

```text
src/
  components/shell/       App chrome, nav, theme
  components/workspace/   Dockview layout + panels
  components/chat/        Chat, composer, model switcher
  components/files/       Project file tree
  components/browser/     Multi-tab viewer
  components/activity/    Activity feed
  lib/                    API clients, chat wiring, layout
docker/nginx.conf         SPA + proxy config
```

If docs disagree with code, prefer `src/`, `docker/nginx.conf`, and `services/workframe-api/server.py`.
