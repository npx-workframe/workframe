#!/usr/bin/env python3
"""Quick TTFT probe: pre-stream phases + upstream first byte/delta (90s cap)."""
from __future__ import annotations

import json
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request

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
    if not room:
        raise SystemExit("no direct room")
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
    if not user:
        raise SystemExit("no room user")

    room_id = str(room["id"])
    ws_id = str(room["workspace_id"])
    user_id = str(user["id"])
    agent_slug = str(room["agent_slug"])

    t = time.perf_counter()
    prof = server._resolve_chat_hermes_profile(agent_slug, user_id, room_id, ws_id)
    print(f"resolve_ms={ms(t)} profile={prof}")

    payload = {
        "room_id": room_id,
        "workspace_id": ws_id,
        "source_id": "ttft-quick",
        "client_id": "ttft-quick",
        "binding_version": 2,
    }
    t = time.perf_counter()
    session = server.profile_chat_session(agent_slug, payload, user_id=user_id)
    sid = str(session.get("session_id") or "")
    print(f"bind_ms={ms(t)} session={sid[:36]}")

    provider = server._llm_billing_provider(prof, user_id=user_id, workspace_id=ws_id)
    model = str(server._read_model_block(prof).get("default") or "")
    print(f"provider={provider} model={model}")

    for i in range(3):
        t = time.perf_counter()
        server._overlay_turn_provider_env(prof, user_id, ws_id, provider, f"quick-{i}")
        server._overlay_turn_user_env(prof, user_id, ws_id, f"quick-{i}")
        print(f"overlay_turn_{i}_ms={ms(t)}")

    port = server._profile_api_port(prof)
    key = server._profile_api_key(prof)
    body = json.dumps(server._profile_turn_payload(prof, "Reply with exactly: pong", room_id)).encode()
    url = f"http://gateway:{port}/api/sessions/{urllib.parse.quote(sid, safe='')}/chat/stream"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    first_byte = first_delta = first_error = None
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            buf = b""
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                if first_byte is None:
                    first_byte = ms(t0)
                buf += chunk
                while b"\n\n" in buf:
                    frame, buf = buf.split(b"\n\n", 1)
                    text = frame.decode("utf-8", errors="replace")
                    ev = ""
                    data = ""
                    for line in text.splitlines():
                        if line.startswith("event:"):
                            ev = line[6:].strip()
                        elif line.startswith("data:"):
                            data = line[5:].lstrip()
                    if ev in ("message.delta", "assistant.delta") and first_delta is None:
                        first_delta = ms(t0)
                        print(f"upstream_first_delta_ms={first_delta}")
                        return 0
                    if ev in ("error", "run.failed", "concierge") and first_error is None:
                        first_error = ms(t0)
                        print(f"upstream_first_error_ms={first_error} data={data[:240]}")
                        return 0
    except urllib.error.HTTPError as exc:
        print(f"upstream_http_error_ms={ms(t0)} code={exc.code} body={exc.read()[:240]!r}")
        return 1
    except OSError as exc:
        print(f"upstream_os_error_ms={ms(t0)} err={exc}")
        return 1

    print(
        f"upstream_first_byte_ms={first_byte} "
        f"first_delta_ms={first_delta} first_error_ms={first_error} "
        f"total_ms={ms(t0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
