# Handoff: Workframe UI

**Status (2026-06-13):** the meta Workframe UI is shipped, running, and wired directly to `workframe-api`. This doc is the current code-grounded reference for the active UI/backend path.

## What it is

Workframe UI is the product shell for a Hermes-backed project:

- Team
- Chat
- Files
- Browser
- Activity

It lives in `packages/workframe-ui/` and is served by the `{slug}-workframe` nginx service. Hermes behavior stays in Hermes. The UI is a thin client over `workframe-api` plus Hermes-native profile API transport.

## Source of truth

Use these files as the current implementation reference:

- `packages/workframe-ui/src/`
- `packages/workframe-ui/docker/nginx.conf`
- `workframe-api/server.py`
- `docker-compose.yml`

If docs disagree with those files, the code wins.

## Runtime shape

```text
Browser
  /api/*                                      -> workframe-api
  /hermes-dashboard/*                         -> Hermes dashboard proxy

workframe-api
  /api/meta                                   -> project/native agent metadata
  /api/agents                                 -> crew list
  /api/routes                                 -> lane metadata (`mode: lane`)
  /api/chat/session                           -> active Hermes session metadata
  /api/chat/messages                          -> history from state.db
  /api/chat/dispatch                          -> lane/session binding metadata write
  /api/chat/stop                              -> stop a running agent (POST, {profile, run_id?})
  /api/chat/steer                             -> steer a running agent (POST, {profile, text, run_id?})
  /api/files/tree|list|read|raw               -> workspace reads
  /api/files/write|upload                     -> workspace writes/uploads
  /api/hermes/profiles/{profile}/bind         -> session + recent history
  /api/hermes/profiles/{profile}/sessions     -> create/resolve session
  /api/hermes/profiles/{profile}/messages     -> non-stream send
  /api/hermes/profiles/{profile}/messages/stream -> live streamed send
  /api/hermes/bootstrap                       -> native dashboard bootstrap/token scrape
```

## What is live today

### Team

- `AgentRailPanel.tsx`
- `useCrew.ts`
- Data comes from `/api/agents`
- On failure the rail empties and surfaces an error; it does not synthesize fake crew data

### Chat

- `ChatSplit.tsx`
- `MessageList.tsx`
- `Composer.tsx` — unified send/stop/steer composer (single textarea + toggle button)
- `chatApi.ts`
- `hermesCatalogApi.ts` — stop/steer API functions
- `HermesSessionContext.tsx`

Current wiring:

- history from `/api/chat/messages`
- session bootstrap from `/api/hermes/profiles/{profile}/sessions` (via `ensureProfileSession`)
- lane metadata from `/api/routes`
- lane binding writes to `/api/chat/dispatch`
- live sends through `/api/hermes/profiles/{profile}/messages/stream`
- profile create/resolve through `/api/hermes/profiles/{profile}/sessions`
- dashboard bootstrap from `/api/hermes/bootstrap` remains available for native dashboard access
- model badge / project meta populated from `/api/meta`
- image attach uploads through `/api/files/upload` and then attaches via Hermes
- **stop**: `POST /api/chat/stop` → `profile_gateway_stop()` → `POST /v1/runs/{run_id}/stop`
- **steer**: `POST /api/chat/steer` → `profile_gateway_steer()` → stop + `POST /v1/runs` with `{"input": text}`
- lane registry auto-update after stream completion (updates binding to latest api_server session)

### Files and Browser

- `ProjectFileTree.tsx`
- `BrowserWorkspaceContext.tsx`
- browser views under `components/browser/`

Current wiring:

- shallow tree from `/api/files/tree`
- lazy folder expansion from `/api/files/list`
- file reads from `/api/files/read`
- raw/media preview from `/api/files/raw`
- saves through `/api/files/write`
- image upload through `/api/files/upload`
- tree, file content, and file state are cached client-side for fast refresh

### Activity

- `ActivityTree.tsx`
- `activityFeed.ts`

Current wiring:

- activity rows are normalized client-side from backend snapshot-style data exposed by `workframe-api`
- click-to-preview: clicking a tool call activity opens a detail view via `GET /api/activity/detail`

## Shell and navigation

`AppShell` provides the chrome, theme toggle, and nav links. Surface links route users to:

- Workframe UI
- Hermes dashboard
- optional legacy mission control
- setup flows

The UI is same-origin in production because nginx proxies both `/api/` and `/hermes-dashboard/`.

## Current caveats

- The meta repo is the real development surface. Fix behavior there first.
- Installer/template parity should be kept in sync immediately after meta behavior changes.
- Mission control may still exist as an optional legacy ops surface, but Workframe UI must not depend on it.
- **No localStorage caching of session IDs** — the BFF lane registry is the single source of truth. Session IDs live in React refs only.

## Session management

- `getSession(profile)` always calls the BFF — no localStorage cache.
- BFF resolves via lane registry → `_latest_session_id()` fallback → create new.
- `useSessionForProfile()` runs once per profile change (guarded by `prevProfileRef`).
- `_latest_session_id()` — any source, most recent first.
- `_latest_api_session_id()` — filters `source='api_server'`, used for lane registry auto-update.
- `_latest_active_run_id()` — filters active run sessions, used for stop/steer.
- Lane registry key: `{source_id}:{client_id}` → `{session_id, gateway_session_id, binding_version, ...}`.
- Native profile uses `binding_version=2`, specialists use `undefined`.

## Dev loop

```powershell
cd D:\Workframe\Workframe\packages\workframe-ui
npm.cmd run build:meta

cd D:\Workframe\Workframe
docker compose up -d
.\scripts\open-workframe-ui.ps1
```

For local HMR:

```powershell
cd D:\Workframe\Workframe\packages\workframe-ui
npm.cmd run dev -- --mode workframe
```

Vite proxies:

- `/api` -> workframe-api
- `/api/hermes/profiles/{profile}/sessions` -> create or resolve per-profile API session
- `/api/hermes/profiles/{profile}/bind` -> session + history bootstrap
- `/api/hermes/profiles/{profile}/messages` -> send message to real Hermes profile runtime
- `/api/hermes/profiles/{profile}/messages/stream` -> stream from real Hermes profile runtime
- `/hermes-dashboard` -> Hermes dashboard

## Practical guidance

- Do not re-implement Hermes routing in the UI.
- Do not bring back per-profile dashboard proxy routing (`/hermes-profiles/*`).
- Do not reintroduce model/provider self-identification in profile SOULs; profiles must identify as their agent names.
- Do not invent mock data when a real endpoint fails.
- Do not patch generated dogfood folders as the source of truth.
- Keep Workframe UI docs aligned to the meta repo implementation, then sync the template copy afterward.
- Do NOT cache session IDs in localStorage. The BFF lane registry is the source of truth.
