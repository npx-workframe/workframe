#!/usr/bin/env python3
"""Granular bind + stream lease timings (docker exec)."""
from __future__ import annotations

import sqlite3
import sys
import time
import uuid

import server


def ms(t0: float) -> int:
    return round((time.perf_counter() - t0) * 1000)


def main() -> int:
    conn = sqlite3.connect(str(server._workframe_db_path()))
    conn.row_factory = sqlite3.Row
    room = conn.execute(
        """
        SELECT id, workspace_id FROM rooms
        WHERE room_type = 'direct' AND deleted_at IS NULL
        ORDER BY updated_at DESC LIMIT 1
        """,
    ).fetchone()
    user = conn.execute(
        "SELECT id FROM users WHERE status = 'active' ORDER BY created_at LIMIT 1",
    ).fetchone()
    conn.close()
    if not room or not user:
        print("no room/user", file=sys.stderr)
        return 1

    uid = str(user["id"])
    rid = str(room["id"])
    ws = str(room["workspace_id"])
    prof = server._resolve_chat_hermes_profile("mybusiness-agent", uid, rid, ws)
    payload = {
        "room_id": rid,
        "workspace_id": ws,
        "source_id": "steps",
        "client_id": "steps",
        "binding_version": 2,
    }
    print(f"profile={prof}")

    block = server._read_model_block(prof)
    t = time.perf_counter()
    block2 = server._read_model_block(prof)
    print(f"read_model_block_ms={ms(t)} repeat_ms={ms(t)}")

    t = time.perf_counter()
    server.ensure_profile_api(prof, uid, ws)
    print(f"ensure_api_ms={ms(t)}")

    provider = server._llm_billing_provider(prof, user_id=uid, workspace_id=ws, block=block)
    run_a, run_b = "steps-a", "steps-b"
    t = time.perf_counter()
    server._apply_turn_credential_lease(prof, uid, ws, provider, run_a)
    print(f"lease_cold_ms={ms(t)} provider={provider}")
    t = time.perf_counter()
    server._apply_turn_credential_lease(prof, uid, ws, provider, run_b)
    print(f"lease_warm_ms={ms(t)}")

    for i in range(3):
        t = time.perf_counter()
        server.profile_chat_session("", payload, user_id=uid)
        print(f"bind_{i}_ms={ms(t)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
