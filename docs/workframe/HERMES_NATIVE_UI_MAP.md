# Hermes native functionality → Workframe UI map

Purpose: keep Workframe UI wired to Hermes without becoming "Hermes CLI in a browser". Workframe surfaces should call Hermes-native APIs/CLI/config where available, and only add BFF middleware where the native surface is missing or too raw for the project harness.

## Implemented / verified in Workframe

### Chat/session lane routing
- Workframe surface: Team rail selects an agent lane; chat panel talks to that profile.
- Current implementation: `AgentRouteContext` + `HermesSessionContext` + BFF `/api/hermes/profiles/{profile}/sessions` and `/messages`/stream endpoints.
- Source of truth: BFF lane registry; no browser session cache.

### Slash palette: Workframe-native command surface
- Workframe surface: composer slash palette.
- Current implementation: `GET /api/hermes/commands`, `POST /api/hermes/commands/exec`.
- Policy: show only commands that are meaningful in Workframe UI. Hide raw profile switching/admin/CLI-only commands until they have a native surface.

### Skills
- Workframe surface: composer Skills button and `/skills` dialog.
- Current implementation: `GET /api/hermes/skills`; selecting a skill sends `/skill <name>` through the active conversation stream.
- Rationale: skill loading affects active conversation context, not a detached Docker exec.

### Model picker
- Workframe surface: composer model chip/dialog and `/model`.
- Current implementation: BFF model catalog + config write path.
- Gap: needs fuller dashboard-style provider/key/OAuth affordances.

### Status / Usage / Debug / Insights / Gquota
- Workframe surface: slash dialogs.
- Current implementation: existing BFF endpoints surfaced through command dialogs.

## Implemented this pass

### Dialog scrollbar policy
- Rule: no scroll-inside-scroll. A dialog shell clips; exactly one inner region scrolls, and that region uses `.wf-scroll`.
- Skills dialog now uses the list as the single scroll container; dialog content itself does not scroll.

### Implemented

#### Stop / Steer (2026-06-11 / 2026-06-13)
- Workframe surface: unified composer with send/stop button + steer textarea.
- Current implementation:
  - `POST /api/chat/stop` → `profile_gateway_stop()` → `POST /v1/runs/{run_id}/stop`
  - `POST /api/chat/steer` → `profile_gateway_steer()` → stop + `POST /v1/runs` with `{"input": text}`
  - `_latest_active_run_id()` finds the active run when no `run_id` is provided.
- UI: When `turnActive=true`, composer button shows Square (stop), textarea placeholder is "Steer the agent…". Sending text during active turn triggers steer. Button click triggers stop.
- These endpoints are wired and functional. They use BFF-native API-server run management, NOT the gateway CLI proxy.

## High-value missing Workframe surfaces

### 1. Create agent profile from Team rail
- Hermes native source: Desktop/dashboard profile APIs:
  - `GET /api/profiles`
  - `POST /api/profiles`
  - `PATCH /api/profiles/{name}`
  - `DELETE /api/profiles/{name}`
  - `GET/PUT /api/profiles/{name}/soul`
  - `GET /api/profiles/{name}/setup-command`
- Existing Hermes desktop UI: `CreateProfileDialog` collects name, clone-from-default, optional SOUL.md.
- Workframe surface: `+ Create agent` button in Team rail header/footer.
- Workframe semantics: create Hermes profile plus Workframe registry/route/avatar entries plus gateway lifecycle. Do not expose raw profile switching in chat.
- Current Workframe state: BFF has profile start/stop/delete and route registry helpers, but no verified create endpoint surfaced in UI.
- Implementation plan:
  1. BFF endpoint `POST /api/hermes/profiles/create` with payload `{ name, display_name, tagline, soul, model?, avatar? }`.
  2. Internally call Hermes profile creation or existing botfather lifecycle helpers; write Workframe registries exactly once.
  3. Start the profile gateway via existing lifecycle path.
  4. UI reloads routes and selects the new profile.

### 2. Agent settings panel for active DM/lane
- Hermes native source: profile info, model config, SOUL.md endpoints, profile rename/delete, setup-command.
- Workframe surface: chat header settings button or panel settings overlay for active agent.
- Should show/edit:
  - display name
  - tagline/role
  - avatar
  - SOUL.md/persona
  - model/provider for that profile
  - gateway status/start/stop
  - delete/retire with confirmation
- Important: model/provider writes should edit that profile config, not global default unless user explicitly chooses global.

### 3. Sessions/history
- Hermes native source: dashboard Sessions page and `hermes sessions` CLI.
- Workframe surface: clock/history icon in chat header for the active lane.
- Should include:
  - recent sessions for active profile
  - search
  - resume/select session
  - rename/export/delete where safe
- Do not surface raw `/resume` in slash palette as the primary UX.

### 4. Config/provider/API keys
- Hermes native source: dashboard Config + API Keys pages; CLI `hermes config`, `hermes auth`, `hermes model`.
- Workframe surface: Settings dialog/panel, not chat commands.
- Should include:
  - provider credentials and OAuth flows
  - model defaults
  - terminal/backend settings where relevant
  - approvals/security/memory/delegation settings
- Secrets must be redacted and never echoed into chat.

### 5. Tools/toolsets
- Hermes native source: dashboard Skills/Toolsets page; CLI `hermes tools`.
- Workframe surface: Skills/tools dialog or settings tab.
- Should include enable/disable toolsets and requirement checks.
- Changes take effect next session; UI should say so.

### 6. MCP
- Hermes native source: dashboard MCP page; CLI `hermes mcp`.
- Workframe surface: Settings → Integrations/MCP.
- Should include add HTTP/stdio server, enable/disable, test, remove, catalog install.

### 7. Cron/jobs
- Hermes native source: dashboard Cron page; CLI `hermes cron`.
- Workframe surface: Jobs/automations panel.
- Should include create/edit/pause/resume/run/delete, delivery target, last/next run.

### 8. Gateway/messaging
- Hermes native source: dashboard messaging/pairing/gateway pages; CLI `hermes gateway`, `hermes pairing`.
- Workframe surface: Settings → Channels.
- Should include platform status, bot token setup, home channel/pairing, restart/status.

### 9. Logs/doctor/status
- Hermes native source: dashboard Logs/Status and CLI `hermes doctor`, `hermes status`.
- Workframe surface: Debug/system panel.
- Should include log tail, component status, doctor checks, version/update status.

### 10. Memory
- Hermes native source: `hermes memory` and dashboard config.
- Workframe surface: Agent settings or Memory tab.
- Should distinguish user memory, profile memory, project knowledge, and skills. Project knowledge belongs in ABKB/Workframe docs, not global memory.

## Principle

If Hermes already has a native command/API, Workframe should import the capability as middleware and translate it into the right Workframe surface. If Hermes only has an interactive CLI/TUI path, do not fake it in chat. Either hide it, mark the API gap, or add an upstream-compatible API endpoint.
