#!/usr/bin/env python3
"""Split provider vs user overlay timing."""
from __future__ import annotations

import sqlite3
import time

import server


def ms(t0: float) -> int:
    return round((time.perf_counter() - t0) * 1000)


def main() -> int:
    conn = sqlite3.connect(str(server.DATA_DIR / "workframe.db"))
    conn.row_factory = sqlite3.Row
    room = conn.execute(
        """
        SELECT r.id, r.workspace_id, ap.slug AS agent_slug
        FROM rooms r
        JOIN agent_profiles ap ON ap.id = r.agent_profile_id
        JOIN room_memberships rm ON rm.room_id = r.id AND rm.status = 'active'
        WHERE r.room_type = 'direct' AND r.deleted_at IS NULL
        ORDER BY r.updated_at DESC
        LIMIT 1
        """,
    ).fetchone()
    user = conn.execute(
        """
        SELECT u.id FROM users u
        JOIN room_memberships rm ON rm.user_id = u.id AND rm.room_id = ?
        WHERE u.status = 'active'
        LIMIT 1
        """,
        (str(room["id"]),),
    ).fetchone()
    conn.close()
    room_id = str(room["id"])
    ws_id = str(room["workspace_id"])
    user_id = str(user["id"])
    prof = server._resolve_chat_hermes_profile(str(room["agent_slug"]), user_id, room_id, ws_id)
    provider = server._llm_billing_provider(prof, user_id=user_id, workspace_id=ws_id)

    for i in range(5):
        t = time.perf_counter()
        server._overlay_turn_provider_env(prof, user_id, ws_id, provider, f"p-{i}")
        p_ms = ms(t)
        t = time.perf_counter()
        server._overlay_turn_user_env(prof, user_id, ws_id, f"u-{i}")
        u_ms = ms(t)
        print(f"turn_{i} provider_ms={p_ms} user_ms={u_ms} total_ms={p_ms + u_ms}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
