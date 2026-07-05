#!/usr/bin/env python3
"""Warm-path timings: model save API return + bind + first stream token."""
from __future__ import annotations

import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request

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
        "source_id": "warm",
        "client_id": "warm",
        "binding_version": 2,
    }
    print(f"profile={prof} healthy={server._profile_api_healthy(prof)}")

    t = time.perf_counter()
    result = server.hermes_model_set(
        prof, "gpt-5.4-medium", user_id=uid, workspace_id=ws, billing_provider="codex",
    )
    print(f"model_set_ms={ms(t)} ok={result.get('ok')}")

    time.sleep(0.5)
    t = time.perf_counter()
    session = server.profile_chat_session("", payload, user_id=uid)
    sid = str(session.get("session_id") or "")
    print(f"bind_ms={ms(t)} session={sid[:28]}")

    t = time.perf_counter()
    server.profile_chat_session("", payload, user_id=uid)
    print(f"bind_repeat_ms={ms(t)}")

    for i in range(2):
        t = time.perf_counter()
        server._reconcile_profile_llm_for_user(prof, uid, ws)
        print(f"reconcile_cached_{i}_ms={ms(t)}")

    t = time.perf_counter()
    server.profile_chat_session("", payload, user_id=uid)
    print(f"bind_cached_ms={ms(t)}")

    port = server._profile_api_port(prof)
    key = server._profile_api_key(prof)
    body = json.dumps(server._profile_turn_payload(prof, "Reply with exactly: pong", rid)).encode()
    url = f"http://gateway:{port}/api/sessions/{sid}/chat/stream"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    t = time.perf_counter()
    first_ms = None
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                if first_ms is None and b"data:" in chunk:
                    first_ms = ms(t)
                    print(f"first_upstream_chunk_ms={first_ms} sample={chunk[:120]!r}")
                    break
    except urllib.error.HTTPError as exc:
        print(f"stream_http_error={exc.code} body={exc.read()[:200]!r}")
        return 1
    if first_ms is None:
        print("no_stream_chunk")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
