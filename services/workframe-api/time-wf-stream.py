#!/usr/bin/env python3
"""WF stream path TTFT with phase breakdown (90s upstream cap)."""
from __future__ import annotations

import io
import json
import sqlite3
import sys
import time
from http.server import BaseHTTPRequestHandler
from typing import Any

import chat_stream
import server


def ms(t0: float) -> int:
    return round((time.perf_counter() - t0) * 1000)


class _CaptureHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def __init__(self) -> None:
        self.events: list[tuple[float, str]] = []
        self.rfile = io.BytesIO()
        self.wfile = _WriteCapture(self)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_response(self, code: int, message: str | None = None) -> None:
        self.status_code = code

    def send_header(self, keyword: str, value: str) -> None:
        pass

    def end_headers(self) -> None:
        self.events.append((time.perf_counter(), "headers"))

    def flush(self) -> None:
        pass


class _WriteCapture(io.BufferedIOBase):
    def __init__(self, handler: _CaptureHandler) -> None:
        self._handler = handler
        self._buf = bytearray()

    def writable(self) -> bool:
        return True

    def write(self, b: bytes) -> int:
        self._buf.extend(b)
        while b"\n\n" in self._buf:
            frame, self._buf = self._buf.split(b"\n\n", 1)
            self._record_frame(frame + b"\n\n")
        return len(b)

    def flush(self) -> None:
        if self._buf:
            self._record_frame(bytes(self._buf))
            self._buf.clear()

    def _record_frame(self, frame: bytes) -> None:
        text = frame.decode("utf-8", errors="replace")
        event = ""
        for line in text.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
        if event:
            self._handler.events.append((time.perf_counter(), event))


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
    if not room or not user:
        print("no room/user", file=sys.stderr)
        return 1

    room_id = str(room["id"])
    ws_id = str(room["workspace_id"])
    user_id = str(user["id"])
    agent_slug = str(room["agent_slug"])

    payload_bind = {
        "room_id": room_id,
        "workspace_id": ws_id,
        "source_id": "wf-ttft",
        "client_id": "wf-ttft",
        "binding_version": 2,
    }
    session = server.profile_chat_session(agent_slug, payload_bind, user_id=user_id)
    sid = str(session.get("session_id") or "")

    handler = _CaptureHandler()
    stream_body = {
        "session_id": sid,
        "text": "Reply with exactly: pong",
        "user_id": user_id,
        "workspace_id": ws_id,
        "room_id": room_id,
    }

    t0 = time.perf_counter()
    try:
        chat_stream.stream_profile_chat(handler, agent_slug, stream_body)
    except Exception as exc:
        print(f"stream_error_ms={ms(t0)} err={exc}")
        return 1

    for at, event in handler.events:
        print(f"  wf_{event}_ms={ms(t0)}")
        if event == "message.delta":
            break
        if event in ("error", "concierge"):
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
