#!/usr/bin/env python3
"""Measure time-to-first-token through the Workframe stream path (docker exec)."""
from __future__ import annotations

import io
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler
from typing import Any

import server


def ms(t0: float) -> int:
    return round((time.perf_counter() - t0) * 1000)


class _CaptureHandler(BaseHTTPRequestHandler):
  protocol_version = "HTTP/1.1"

  def __init__(self) -> None:
    self.headers_sent = False
    self.events: list[tuple[float, str, str]] = []
    self._t0 = time.perf_counter()
    self.rfile = io.BytesIO()
    self.wfile = _WriteCapture(self)

  def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
    return

  def send_response(self, code: int, message: str | None = None) -> None:
    self.status_code = code

  def send_header(self, keyword: str, value: str) -> None:
    pass

  def end_headers(self) -> None:
    self.headers_sent = True
    self.events.append((time.perf_counter(), "headers", ""))


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
    data = ""
    for line in text.splitlines():
      if line.startswith("event:"):
        event = line[6:].strip()
      elif line.startswith("data:"):
        data = line[5:].lstrip()
    self._handler.events.append((time.perf_counter(), event, data))


def _find_room_user() -> tuple[dict[str, Any], str]:
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
    conn.close()
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
  return dict(room), str(user["id"])


def _report_handler_events(handler: _CaptureHandler, t0: float, label: str) -> int | None:
  first_delta: int | None = None
  for at, event, _data in handler.events:
    rel = ms(t0)
    if event in ("run.started", "message.delta", "error", "concierge", "message.complete", "done"):
      print(f"  {label}_{event}_ms={rel}")
    if event == "message.delta" and first_delta is None:
      first_delta = rel
  return first_delta


def _stream_upstream(prof: str, sid: str, text: str, room_id: str) -> dict[str, int | None]:
  port = server._profile_api_port(prof)
  key = server._profile_api_key(prof)
  body = json.dumps(server._profile_turn_payload(prof, text, room_id)).encode()
  url = f"http://gateway:{port}/api/sessions/{urllib.parse.quote(sid, safe='')}/chat/stream"
  req = urllib.request.Request(
    url,
    data=body,
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    method="POST",
  )
  t0 = time.perf_counter()
  out: dict[str, int | None] = {
    "first_byte_ms": None,
    "first_delta_ms": None,
    "run_started_ms": None,
  }
  try:
    with urllib.request.urlopen(req, timeout=120) as resp:
      buf = b""
      while True:
        chunk = resp.read(4096)
        if not chunk:
          break
        if out["first_byte_ms"] is None:
          out["first_byte_ms"] = ms(t0)
        buf += chunk
        while b"\n\n" in buf:
          frame, buf = buf.split(b"\n\n", 1)
          event = ""
          for line in frame.decode("utf-8", errors="replace").splitlines():
            if line.startswith("event:"):
              event = line[6:].strip()
          if event == "run.started" and out["run_started_ms"] is None:
            out["run_started_ms"] = ms(t0)
          if event in ("message.delta", "assistant.delta") and out["first_delta_ms"] is None:
            out["first_delta_ms"] = ms(t0)
            return out
  except urllib.error.HTTPError as exc:
    print(f"upstream_http_error={exc.code} body={exc.read()[:240]!r}")
  except OSError as exc:
    print(f"upstream_error={exc}")
  return out


def main() -> int:
  import chat_stream

  room, user_id = _find_room_user()
  room_id = str(room["id"])
  workspace_id = str(room["workspace_id"])
  agent_slug = str(room["agent_slug"])
  payload_bind = {
    "room_id": room_id,
    "workspace_id": workspace_id,
    "source_id": "ttft",
    "client_id": "ttft",
    "binding_version": 2,
  }

  t_resolve = time.perf_counter()
  prof = server._resolve_chat_hermes_profile(agent_slug, user_id, room_id, workspace_id)
  print(f"agent_slug={agent_slug} profile={prof} resolve_ms={ms(t_resolve)}")

  healthy_before = server._profile_api_healthy(prof)
  print(f"profile_api_healthy_before={healthy_before}")

  t_bind = time.perf_counter()
  session = server.profile_chat_session(agent_slug, payload_bind, user_id=user_id)
  print(f"bind_ms={ms(t_bind)} session={str(session.get('session_id') or '')[:36]}")

  provider = server._llm_billing_provider(prof, user_id=user_id, workspace_id=workspace_id)
  model_block = server._read_model_block(prof)
  model = str(model_block.get("default") or "")

  # Phase timings (same work as stream_profile_chat pre-upstream)
  t_auth = time.perf_counter()
  import run_authority
  import run_ledger

  run_ledger.ensure_schema()
  auth_req = run_authority.chat_run_request(
    triggering_user_id=user_id,
    profile_slug=prof,
    workspace_id=workspace_id,
    provider=provider,
    room_id=room_id,
  )
  auth_ctx = chat_stream._run_authority_context_for_chat(user_id, workspace_id, provider)
  run_authority.evaluate_run_authority(auth_req, auth_ctx, run_id="ttft-probe")
  print(f"authority_ms={ms(t_auth)} provider={provider} model={model}")

  t_api = time.perf_counter()
  server.ensure_profile_api(prof, user_id, workspace_id)
  ensure_ms = ms(t_api)
  print(f"ensure_profile_api_ms={ensure_ms} healthy_after={server._profile_api_healthy(prof)}")

  t_overlay = time.perf_counter()
  server._overlay_turn_provider_env(prof, user_id, workspace_id, provider, "ttft-overlay")
  server._overlay_turn_user_env(prof, user_id, workspace_id, "ttft-overlay")
  print(f"overlay_ms={ms(t_overlay)}")

  sid = str(session.get("session_id") or "")
  stream_body = {
    "session_id": sid,
    "text": "Reply with exactly: pong",
    "user_id": user_id,
    "workspace_id": workspace_id,
    "room_id": room_id,
  }

  # Full Workframe stream path
  handler = _CaptureHandler()
  t_stream = time.perf_counter()
  chat_stream.stream_profile_chat(handler, agent_slug, stream_body)
  wf_ttft = _report_handler_events(handler, t_stream, "wf")
  print(f"wf_ttft_ms={wf_ttft}")

  # Direct upstream (gateway only) for comparison
  upstream = _stream_upstream(prof, sid, "Reply with exactly: pong", room_id)
  print(
    "upstream "
    + " ".join(f"{k}={v}" for k, v in upstream.items() if v is not None)
  )
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
