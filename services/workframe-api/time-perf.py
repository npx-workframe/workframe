#!/usr/bin/env python3
"""Measure model-save, gateway reload, bind, and reconcile latency (docker exec)."""
from __future__ import annotations

import sqlite3
import sys
import time

import server


def ms(t0: float) -> int:
    return round((time.perf_counter() - t0) * 1000)


def main() -> int:
    conn = sqlite3.connect(str(server._workframe_db_path()))
    conn.row_factory = sqlite3.Row
    room = conn.execute(
        """
        SELECT r.id, r.workspace_id
        FROM rooms r
        WHERE r.room_type = 'direct' AND r.deleted_at IS NULL
        ORDER BY r.updated_at DESC
        LIMIT 1
        """,
    ).fetchone()
    user = conn.execute(
        "SELECT id FROM users WHERE status = 'active' ORDER BY created_at LIMIT 1",
    ).fetchone()
    conn.close()
    if not room or not user:
        print("no room/user", file=sys.stderr)
        return 1

    user_id = str(user["id"])
    room_id = str(room["id"])
    ws_id = str(room["workspace_id"])
    prof = server._resolve_chat_hermes_profile("mybusiness-agent", user_id, room_id, ws_id)
    print(f"profile={prof}")

    t = time.perf_counter()
    ok, err = server._apply_model_persisted(
        prof, "codex", "gpt-5.4-mini", user_id, restart_gateway=False,
    )
    print(f"yaml_write_ms={ms(t)} ok={ok} err={err!r}")

    t = time.perf_counter()
    code, out = server._gateway_exec(prof, ["gateway", "restart"])
    # ponytail: ~7s vs stop+start ~45s on dogfood
    healthy = server._wait_profile_api_healthy(prof, attempts=24, delay=0.25)
    print(f"gateway_restart_ms={ms(t)} code={code} healthy={healthy} out={out[:80]!r}")

    t = time.perf_counter()
    changed = server._reconcile_profile_llm_for_user(prof, user_id, ws_id)
    print(f"reconcile_ms={ms(t)} changed={changed}")

    t = time.perf_counter()
    server.ensure_profile_api(prof, user_id, ws_id)
    print(f"ensure_api_ms={ms(t)}")

    payload = {
        "room_id": room_id,
        "workspace_id": ws_id,
        "source_id": "perf",
        "client_id": "perf",
        "binding_version": 2,
    }
    t = time.perf_counter()
    session = server.profile_chat_session("", payload, user_id=user_id)
    print(f"bind_ms={ms(t)} session={str(session.get('session_id') or '')[:24]}")

    t = time.perf_counter()
    changed2 = server._reconcile_profile_llm_for_user(prof, user_id, ws_id)
    print(f"reconcile_repeat_ms={ms(t)} changed={changed2}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
