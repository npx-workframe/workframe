# Hermes ↔ BFF route map

UI surface → BFF endpoint → Hermes artifact → status.

See **`RUNTIME_OPERATIONS.md`** for secure mode, supervisor, provider gating, and space `@mentions`.

**Adapter program (planned, 2026-06-26):** [adapters-overview.md](./adapters-overview.md) · [adapter-build-roadmap.md](./adapter-build-roadmap.md) · [adapter-external-references.md](./adapter-external-references.md) — step 1 adds `runtime_kind` so chat can target external NemoHermes (`:8642`) instead of always `gateway:{port}`.

| UI surface | BFF endpoint | Hermes / store artifact | Status |
|------------|--------------|-------------------------|--------|
| User profile (rail bottom) | `PATCH /api/me` | zk `profiles` + `workframe.db` users mirror | **Real** |
| Connect accounts tab | `GET /api/me/providers`, `POST /api/me/credentials`, disconnect, `POST /api/me/oauth/:id/start` | User Hermes home `profiles/{user_slug}/.env` + `auth.json` | **Real** |
| Connect accounts (owner/admin) | same + `source: stack` | Stack keys from `workframe-agent/.env` | **Real** |
| Team gear → Workspace | `GET /api/workspace/:id/members`, `/invites`, `DELETE /api/workspace/:id/members` | `workframe.db` memberships | **Real** |
| Add Contact | `POST /api/workspace/:id/invites` | `workspace_invites` | **Real** |
| Chat gear → Agent | `GET /api/hermes/models`, `POST /api/hermes/model`, `GET /api/hermes/profiles/status` | Profile `config.yaml`, gateway state | **Real** |
| Chat gear → Space | `GET /api/rooms/:id/members`, `DELETE /api/rooms/:id/members` | `room_memberships` | **Real** (no PATCH room name/topic yet) |
| Chat gear → DM | — | Room metadata only | **Read-only** |
| Composer model picker | `GET /api/hermes/models`, `POST /api/hermes/model` | Filtered by `connected_providers`; empty state → Connect accounts | **Real** |
| Composer (no provider) | — | `has_llm_provider: false`; CTA opens profile Connect tab | **Real** |
| Space chat + @agent | `POST /api/rooms/:id/messages/send` | SQLite `messages`; mention → server Hermes stream → room live SSE → final insert | **Real** |
| Room live agent stream | `GET /api/rooms/:id/live` (SSE) | In-memory fanout: `turn.started` / `turn.update` / `turn.complete` | **Real** |
| Workspace live refresh | `GET /api/workspace/:wid/events` (SSE) | Revision from rooms/messages/memberships | **Real** |
| Composer skills | `GET /api/hermes/skills` | Hermes skills dir | **Real** |
| Create Agent | `POST /api/hermes/profiles/create` | `hermes profile create` in gateway container | **Real** |
| Hermes dashboard link | proxied `/hermes-dashboard/` | Dashboard nginx → gateway :9119 | **Real** |
| Header Dashboard / Setup | env surface links | Hermes dashboard / setup | **Real** |
| Footer status bar | — | — | **Placeholder** (badges later) |
| Workspace admin keys / BYOK policy | `credential_bindings`, grants schema | workspace + user `.env` | **Deferred** |
| Per-user credential at stream | `_overlay_turn_provider_env` + `_resolve_credential(..., user_only=True)` | Specialist profile `.env` per turn; `user_only` providers skip workspace fallback | **Real** (ponytail: races on shared profile) |
| Stripe (payments) | `PROVIDER_CONNECT_CATALOG` + `/internal/action/stripe/*` | Vault + turn lease → Stripe API | **Planned** ([adapter-step1](./adapter-step1-runtime-seam.md)) |
| Agent runtime kind | `agent_profiles.runtime_kind` | `compose_hermes` vs `nemohermes` host resolver | **Planned** ([adapter-step1](./adapter-step1-runtime-seam.md)) |
| Agent SOUL edit in UI | — | `SOUL.md` per profile | **Deferred** |
| Space name/topic edit | — | `rooms` table | **Deferred** (no PATCH endpoint) |
| DM block / clear history | — | `messages` / memberships | **Deferred** |

Hermes docs: https://hermes-agent.nousresearch.com/docs/
