#!/usr/bin/env python3
"""Time bind + credential lease on running workframe-api (docker exec)."""
from __future__ import annotations

import sqlite3
import sys
import time

import server


def main() -> int:
    conn = sqlite3.connect(str(server.DATA_DIR / "workframe.db"))
    conn.row_factory = sqlite3.Row
    room = conn.execute(
        """
        SELECT r.id, r.workspace_id, r.agent_profile_id, ap.slug AS agent_slug
        FROM rooms r
        JOIN agent_profiles ap ON ap.id = r.agent_profile_id
        JOIN room_memberships rm ON rm.room_id = r.id AND rm.status = 'active'
        WHERE r.room_type = 'direct' AND r.deleted_at IS NULL
          AND ap.slug = 'workframe-agent'
        ORDER BY r.updated_at DESC
        LIMIT 1
        """,
    ).fetchone()
    if not room:
        print("no workframe-agent room", file=sys.stderr)
        return 1
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
    if not room or not user:
        print("no room/user", file=sys.stderr)
        return 1

    user_id = str(user["id"])
    room_id = str(room["id"])
    workspace_id = str(room["workspace_id"])
    payload = {
        "room_id": room_id,
        "workspace_id": workspace_id,
        "source_id": "timing",
        "client_id": "timing",
        "binding_version": 2,
    }

    t_rt = time.perf_counter()
    prof = server._resolve_chat_hermes_profile("workframe-agent", user_id, room_id, workspace_id)
    rt_ms = (time.perf_counter() - t_rt) * 1000
    print(f"resolve_runtime_ms={rt_ms:.0f} profile={prof}")

    provider = server._llm_billing_provider(prof)
    t_api = time.perf_counter()
    server.ensure_profile_api(prof, user_id, workspace_id)
    api_ms = (time.perf_counter() - t_api) * 1000
    t_llm = time.perf_counter()
    server._overlay_chat_llm_env(prof, user_id, workspace_id, provider)
    llm_ms = (time.perf_counter() - t_llm) * 1000
    print(f"ensure_profile_api_ms={api_ms:.0f} overlay_llm_ms={llm_ms:.0f}")

    t0 = time.perf_counter()
    session = server.profile_chat_session("workframe-agent", payload, user_id=user_id)
    session_ms = (time.perf_counter() - t0) * 1000
    sid = str(session.get("session_id") or "")
    print(f"session_ms={session_ms:.0f} session={sid[:40]}")

    t_hist = time.perf_counter()
    history = server.chat_messages(prof, sid)
    hist_ms = (time.perf_counter() - t_hist) * 1000
    print(f"history_ms={hist_ms:.0f} messages={len(history.get('messages') or [])}")

    healthy = server._profile_api_healthy(prof)
    print(f"profile_api_healthy={healthy} port={server._profile_api_port(prof)}")

    run_a = "timing-run-a"
    run_b = "timing-run-b"
    t1 = time.perf_counter()
    server._apply_turn_credential_lease(prof, user_id, workspace_id, provider, run_a)
    lease1_ms = (time.perf_counter() - t1) * 1000
    t2 = time.perf_counter()
    server._apply_turn_credential_lease(prof, user_id, workspace_id, provider, run_b)
    lease2_ms = (time.perf_counter() - t2) * 1000
    print(f"lease_cold_ms={lease1_ms:.0f} lease_reuse_ms={lease2_ms:.0f} provider={provider}")

    _, model = server._read_model_from_config(prof)
    print(f"model={model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
