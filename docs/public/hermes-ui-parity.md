# Hermes UI parity map

Purpose: wire Workframe UI to Hermes-native APIs without turning the browser into a raw Hermes CLI.

Policy: call Hermes APIs/config where they exist; add BFF middleware only when the native surface is missing or too raw for the project harness.

## Implemented

| Surface | BFF / UI path | Notes |
|---------|---------------|-------|
| Agent lane chat | `HermesSessionContext` + `/api/hermes/profiles/{profile}/…` | Room-scoped bind + stream |
| Slash commands | `GET/POST /api/hermes/commands` | Workframe-native subset only |
| Skills | `GET /api/hermes/skills` | Sends `/skill` through active stream |
| Model picker | `/api/hermes/models`, config write | Requires connected providers |
| Stop / steer | `POST /api/chat/stop`, `/api/chat/steer` | BFF run management |
| Status / usage dialogs | Existing BFF endpoints via slash palette | |
| Create agent | `POST /api/hermes/profiles/create` | Team rail + gateway lifecycle |
| Connect accounts | `/api/me/providers`, OAuth + credential routes | User Hermes home `.env` |

## Gaps (high value)

| Surface | Hermes source | Workframe target |
|---------|---------------|------------------|
| Agent settings | Profile SOUL/model/config APIs | Chat header settings for active lane |
| Session history | Dashboard sessions, `hermes sessions` | History icon — resume/rename/delete |
| Provider / config | Dashboard config, `hermes auth` | Settings dialog — never echo secrets in chat |
| Toolsets | Dashboard toolsets, `hermes tools` | Skills/tools settings tab |
| MCP | Dashboard MCP, `hermes mcp` | Settings → Integrations |
| Cron | Dashboard cron, `hermes cron` | Jobs/automations panel |
| Channels | Gateway/pairing pages | Settings → Channels |
| Logs / doctor | Dashboard logs, `hermes doctor` | Debug panel |
| Memory | `hermes memory` | Distinguish user vs profile vs **project docs in `/workspace`** |

## Principle

If Hermes has a native API, Workframe should wrap it for the right UI surface. If Hermes only exposes an interactive CLI/TUI, do not fake it in chat — hide it, document the gap, or add an upstream-compatible API endpoint.

See also: [BFF route map](./bff-route-map.md).
