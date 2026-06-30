# workframe-ui

Product shell SPA for Workframe — chat, files, browser, activity. Served by nginx in the `{slug}-workframe` compose service.

**Reference docs:** [`../../../workframe.md`](../../../workframe.md) §17, [`../create-workframe/docs/handoffs/frontend-workframe-ui.md`](../create-workframe/docs/handoffs/frontend-workframe-ui.md)

## Stack

Vite 8 · React 19 · TypeScript · Dockview · shadcn/ui · Tailwind 4 · Lucide

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Vite dev server (HMR) |
| `npm run build:meta` | Production build with `.env.workframe` (meta Workframe ports) |
| `npm run build:aifred` | Production build with `.env.aifred` (AIfred dogfood ports) |
| `npm run deploy:dogfood` | `build:aifred` + copy `dist/` → `../../../AIfred/workframe-ui/public/` |
| `npm run build` | Generic production build |

## Meta dev loop

```powershell
cd D:\Workframe\Workframe\packages\workframe-ui
npm.cmd install
npm.cmd run build:meta

cd D:\Workframe\Workframe
docker compose up -d
.\scripts\open-workframe-ui.ps1
```

Meta compose mounts `./packages/workframe-ui/dist` and `./packages/workframe-ui/docker/nginx.conf` on `WORKFRAME_UI_PORT` (default 18644).

## Runtime wiring

In production, nginx serves the SPA and proxies:

- `/api/*` -> same-origin auth surface on `workframe-workframe` (proxied to `workframe-api` internally)
- `/hermes-dashboard/*` -> Hermes dashboard, including WebSockets

In development, `vite.config.ts` mirrors the same routing through the local dev server.

Current live data paths:

- project metadata from `/api/meta`
- crew list from `/api/agents`
- chat session/history from `/api/chat/session` and `/api/chat/messages`
- files/browser from `/api/files/*`
- lane/session binding via `/api/chat/dispatch` and `/api/chat/resolve`
- per-profile bind/create/send/stream via `/api/hermes/profiles/{profile}/bind|sessions|messages|messages/stream`
- Hermes dashboard bootstrap from `/api/hermes/bootstrap` remains available for native dashboard access

## Multi-lane behavior

- One Workframe UI shell, one Hermes dashboard surface, one gateway container.
- Each lane targets a real Hermes profile API runtime managed through `workframe-api`.
- Specialist lanes use `workframe-api` directly for bind/send/stream flows; they do not submit prompts through legacy mission-control paths.
- Session persistence is keyed by `profile + source_id + client_id`, so:
  - one browser keeps its own lane sessions,
  - another browser/device gets separate sessions,
  - other channels like Telegram remain separate too.
- Session titles are created per lane and auto-deduplicated when Hermes requires unique titles:
  - `Session with Dev`
  - `Session with Dev (2)`

## Agent identity

- Each profile is backed by its own `SOUL.md` and `profile.yaml` manifest.
- Workframe profiles are explicitly instructed to identify as their agent name/role, never as the underlying model, provider, `OWL`, or a generic Hermes assistant.
- The native profile remains the only messaging-owning gateway; specialist profile gateways run API-only.

## Env files

Build-time only:

- `.env.workframe` — meta project name and port values
- `.env.aifred` — dogfood project name and port values

## Structure

```text
src/
  components/shell/       App chrome, nav links, theme
  components/workspace/   Dockview layout + panels
  components/chat/        Chat + composer + model switcher
  components/files/       Project file tree
  components/browser/     Multi-tab file viewer
  components/activity/    Activity feed
  lib/                    API clients, chat wiring, layout engine, helpers
docker/nginx.conf         SPA server + same-origin proxy config
scripts/copy-dogfood.mjs  Deploy dist to generated project
```

## Notes

- The meta repo is the source of truth for UI behavior.
- Dogfood copy is for install-path testing, not primary development.
- If docs drift from code, prefer `src/`, `docker/nginx.conf`, and `workframe-api/server.py`.
