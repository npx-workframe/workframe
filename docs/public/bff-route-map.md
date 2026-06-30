# Hermes ↔ BFF route map

UI surface → BFF endpoint → backing store → status.

Operational context: [Runtime operations](./runtime-operations.md).  
**Note:** The Workframe API is an internal BFF — endpoint shapes are not a stable public contract.

| UI surface | BFF endpoint | Store / artifact | Status |
|------------|--------------|------------------|--------|
| User profile (rail) | `PATCH /api/me` | zk profiles + `workframe.db` | **Real** |
| Connect accounts | `GET /api/me/providers`, credential/OAuth routes | User Hermes home `.env` + `auth.json` | **Real** |
| Connect (owner/admin) | same + `source: stack` | Stack keys on native profile | **Real** |
| Team → Workspace | `/api/workspace/:id/members`, invites | `workframe.db` | **Real** |
| Chat gear → Agent | `/api/hermes/models`, model + status | Profile `config.yaml` | **Real** |
| Chat gear → Space | room members CRUD | `room_memberships` | **Real** (no PATCH name/topic) |
| Composer model picker | `/api/hermes/models`, `POST /api/hermes/model` | Filtered by connected providers | **Real** |
| Space chat + @agent | `POST /api/rooms/:id/messages/send` | SQLite + Hermes stream + room SSE | **Real** |
| Room live stream | `GET /api/rooms/:id/live` | In-memory SSE fanout | **Real** |
| Workspace refresh | `GET /api/workspace/:wid/events` | SSE revision | **Real** |
| Composer skills | `GET /api/hermes/skills` | Hermes skills dir | **Real** |
| Create Agent | `POST /api/hermes/profiles/create` | `hermes profile create` in gateway | **Real** |
| Hermes dashboard | `/hermes-dashboard/` proxy | Dashboard nginx | **Real** (owner/admin gated in public mode) |
| Footer status bar | — | — | **Placeholder** |
| Per-user credential at stream | `_overlay_turn_provider_env` | Specialist `.env` per turn | **Real** (shared-profile race ceiling) |
| Workspace BYOK policy UI | grants schema | workspace + user env | **Deferred** |
| Agent SOUL edit in UI | — | `SOUL.md` | **Deferred** |
| Space name/topic edit | — | `rooms` table | **Deferred** |
| Stripe payments | `/internal/action/stripe/*` | Vault + lease | **Planned** |
| External runtime adapter | `runtime_kind` resolver | NemoHermes / external host | **Planned** (not in core BFF yet) |

Hermes upstream docs: https://hermes-agent.nousresearch.com/docs/
