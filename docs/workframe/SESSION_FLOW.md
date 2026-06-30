# Workframe Session Flow — Source of Truth

> **Updated 2026-06-23:** Canonical architecture is in [`session-architecture.md`](./session-architecture.md) (mermaid diagrams, SSOT table). This file is kept for historical grep hits.

## Quick reference

- **Room agent DM:** `POST /api/hermes/profiles/{template}/bind` with `room_id` → `room_sessions` → Hermes `state.db`
- **UI:** `HermesSessionContext` bind once per room; `stateDbSidRef` for sends; no `localStorage` session cache
- **Lane registry:** derived cache only when `room_id` is set
- **Identity:** `client_id` in localStorage (`chatSession.ts`); `binding_version=2` for native template only

See [`CHANGES-2026-06-23-session-vault.md`](./CHANGES-2026-06-23-session-vault.md) for the recent fix list.
