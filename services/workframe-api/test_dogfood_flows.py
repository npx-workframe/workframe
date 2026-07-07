#!/usr/bin/env python3
"""Dogfood API smoke — rooms, mention, session, invite, OTP, agent, project.

Run against live stack:
  python test_dogfood_flows.py --base http://127.0.0.1:18644

Mention tests default to invoke_agents=False (routing only, no LLM spend).
Pass --live-mention to invoke agents; dogfood should bill via Codex gpt-5.4-mini.

Requires WORKFRAME_E2E=1 + install window OR DEV_LOCAL_UNSAFE for OTP in auth/start response.
Falls back to zk session mint when --data-dir points at install data (same host as API).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _req(
    base: str,
    method: str,
    path: str,
    *,
    body: dict | None = None,
    cookie: str = "",
    session_id: str = "",
    timeout: float = 60,
) -> tuple[int, dict[str, Any]]:
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if session_id and not cookie:
        import zk_auth

        os.environ.setdefault("WORKFRAME_API_DATA_DIR", r"D:\ab\projects\MyBusiness\workframe-api\data")
        os.environ.setdefault("WORKFRAME_INSTALL_ID", "wf_06f00ed848c3")
        cookie = f"{zk_auth.session_cookie_name()}={session_id}"
    if cookie:
        headers["Cookie"] = cookie
    if session_id:
        headers["X-Workframe-Session"] = session_id
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {"error": exc.reason}
        except json.JSONDecodeError:
            payload = {"error": raw or str(exc)}
        return exc.code, payload


def _mint_session_cookie(data_dir: Path, user_id: str) -> tuple[str, str]:
    """Return (cookie_header, session_id) for API auth."""
    import zk_auth

    os.environ["WORKFRAME_API_DATA_DIR"] = str(data_dir)
    os.environ["WORKFRAME_INSTALL_ID"] = "wf_06f00ed848c3"

    # Read-only sqlite — avoid WAL sidecars on the shared data mount.
    db_path = data_dir / "zk_auth.db"
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT s.id
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.user_id = ?
              AND s.revoked_at IS NULL
              AND s.expires_at > datetime('now')
              AND u.status = 'active'
            ORDER BY s.created_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    session_id = str(row["id"]) if row else ""
    if not session_id:
        raise RuntimeError(f"no valid session for user {user_id}")
    cookie_name = zk_auth.session_cookie_name()
    return f"{cookie_name}={session_id}", session_id


def _pick_user(data_dir: Path) -> tuple[str, str]:
    db = data_dir / "workframe.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT u.id, u.email
        FROM users u
        JOIN workspace_memberships m ON m.user_id = u.id AND m.deleted_at IS NULL
        WHERE u.deleted_at IS NULL AND m.role IN ('owner', 'admin')
        ORDER BY CASE m.role WHEN 'owner' THEN 0 ELSE 1 END, u.created_at ASC
        LIMIT 1
        """
    ).fetchone()
    if not row:
        row = conn.execute(
            "SELECT id, email FROM users WHERE deleted_at IS NULL ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
    conn.close()
    if not row:
        raise SystemExit("no users in workframe.db")
    return str(row["id"]), str(row["email"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:18644")
    ap.add_argument("--data-dir", default=r"D:\ab\projects\MyBusiness\workframe-api\data")
    ap.add_argument("--email", default="")
    ap.add_argument("--live-mention", action="store_true", help="invoke agents on @mention (Codex gpt-5.4-mini; costs tokens)")
    args = ap.parse_args()
    base = args.base
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        mark = "ok" if ok else "FAIL"
        print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
        if not ok:
            failures.append(name)

    code, meta = _req(base, "GET", "/api/meta")
    check("meta", code == 200 and meta.get("ok"), str(meta.get("error") or meta.get("project_name")))

    cookie = ""
    session_id = ""
    user_id = ""
    email = args.email.strip().lower()

    def api(method: str, path: str, body: dict | None = None, *, timeout: float = 60) -> tuple[int, dict[str, Any]]:
        return _req(base, method, path, body=body, cookie=cookie, session_id=session_id, timeout=timeout)

    if args.data_dir:
        data_dir = Path(args.data_dir)
        user_id, db_email = _pick_user(data_dir)
        if not email:
            email = db_email
        try:
            cookie, session_id = _mint_session_cookie(data_dir, user_id)
            check("session mint", bool(session_id), user_id)
        except Exception as exc:  # noqa: BLE001
            check("session mint", False, str(exc))

    if not session_id and not cookie:
        if not email:
            email = f"smoke-{uuid.uuid4().hex[:8]}@workframe.test"
        code, start = api("POST", "/api/auth/start", body={"email": email})
        otp = str(start.get("otp_code") or "")
        check("auth/start", code == 200 and start.get("ok"), start.get("error") or ("otp" if otp else "no otp"))
        if otp:
            code, verify = api("POST", "/api/auth/verify", body={"email": email, "code": otp})
            check("auth/verify", code == 200 and verify.get("ok"), verify.get("error") or "")
            user_id = str(verify.get("user_id") or "")
            session_id = str(verify.get("session_id") or "")
            if session_id:
                import zk_auth

                cookie = f"{zk_auth.session_cookie_name()}={session_id}"
            elif args.data_dir and user_id:
                cookie, session_id = _mint_session_cookie(Path(args.data_dir), user_id)

    if not session_id:
        raise SystemExit("no session — pass --data-dir or enable OTP exposure")

    code, me = api("GET", "/api/me")
    me_user = me.get("user") if isinstance(me.get("user"), dict) else me
    check("me", code == 200 and (me.get("ok", True) or me_user.get("id")), me.get("error") or str(me_user.get("email") or me_user.get("id")))
    user_id = str(me_user.get("id") or me_user.get("user_id") or user_id)

    workspaces = me.get("workspaces") if isinstance(me.get("workspaces"), list) else []
    current_ws = me.get("current_workspace") if isinstance(me.get("current_workspace"), dict) else None
    ws_id = str((current_ws or {}).get("id") or (workspaces[0].get("id") if workspaces else "") or "")
    if not ws_id and args.data_dir:
        conn = sqlite3.connect(str(Path(args.data_dir) / "workframe.db"))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT workspace_id FROM workspace_memberships WHERE user_id = ? AND deleted_at IS NULL LIMIT 1",
            (user_id,),
        ).fetchone()
        conn.close()
        if row:
            ws_id = str(row["workspace_id"])
    if not ws_id:
        code, snap = api("GET", "/api/snapshot")
        ws = snap.get("workspace") if isinstance(snap.get("workspace"), dict) else {}
        ws_id = str(ws.get("id") or "")
    check("workspace", bool(ws_id), ws_id or "missing")

    code, rooms_payload = api("GET", f"/api/workspace/{ws_id}/rooms")
    if rooms_payload.get("error") == "workspace_not_found":
        slug_candidates = ["default"]
        if workspaces:
            slug_candidates.extend(str(ws.get("slug") or "") for ws in workspaces)
        for alt in slug_candidates:
            if not alt or alt == ws_id:
                continue
            code, rooms_payload = api("GET", f"/api/workspace/{alt}/rooms")
            if code == 200:
                ws_id = str(rooms_payload.get("workspace_id") or ws_id)
                break
    rooms = rooms_payload.get("rooms") or []
    check("list rooms", code == 200 and isinstance(rooms, list), f"count={len(rooms)}")

    channel = next((r for r in rooms if r.get("room_type") == "channel"), rooms[0] if rooms else None)
    room_id = str(channel.get("id") if channel else "")
    check("pick channel room", bool(room_id), room_id)

    # Create project (room)
    proj_slug = f"smoke-{int(time.time())}"
    code, proj = api(
        "POST",
        f"/api/workspace/{ws_id}/rooms/create",
        body={"name": f"Smoke {proj_slug}", "slug": proj_slug, "topic": "smoke test", "room_type": "channel"},
    )
    check("create project", code in (200, 201) and proj.get("ok"), proj.get("error") or str(proj.get("room_id")))

    # Create agent
    agent_slug = f"smoke-agent-{int(time.time()) % 100000}"
    code, agent = api(
        "POST",
        "/api/hermes/profiles/create",
        body={
            "name": agent_slug,
            "display_name": "Smoke Agent",
            "workspace_id": ws_id,
            "role": "helper",
            "model": "gpt-5.4-mini",
        },
        timeout=180,
    )
    check("create agent", code == 200 and agent.get("ok"), agent.get("error") or str(agent.get("profile")))

    # Invite email
    invite_email = f"invite-{uuid.uuid4().hex[:6]}@workframe.test"
    code, inv = api(
        "POST",
        f"/api/workspace/{ws_id}/invites",
        body={"email": invite_email, "role": "member"},
    )
    check("invite email", code in (200, 201) and inv.get("ok"), inv.get("error") or invite_email)

    # Add contact = bootstrap DM with native agent template
    native = str(meta.get("native_profile") or "workframe-agent")
    code, dm = api(
        "POST",
        f"/api/hermes/profiles/{native}/bootstrap-dm",
        body={"workspace_id": ws_id},
        timeout=120,
    )
    check("add contact (bootstrap-dm)", code == 200 and dm.get("ok"), dm.get("error") or str(dm.get("room_id")))

    # New session — UI uses room bind with new_session, not activate with a fresh uuid.
    if room_id:
        code, sessions = api("GET", f"/api/rooms/{room_id}/sessions")
        check("list sessions", code == 200, str(len(sessions.get("sessions") or [])))
        code, bound = api(
            "POST",
            f"/api/rooms/{room_id}/bind",
            body={
                "source_id": "room",
                "client_id": room_id,
                "new_session": True,
            },
            timeout=120,
        )
        new_sid = str(bound.get("session_id") or "")
        check("new session", code == 200 and bound.get("ok") and bool(new_sid), bound.get("error") or new_sid)
        if new_sid:
            code, activated = api(
                "POST",
                f"/api/rooms/{room_id}/sessions/activate",
                body={"session_id": new_sid, "source_id": "room", "client_id": room_id},
            )
            check("activate session", code == 200 and activated.get("ok"), activated.get("error") or "")

        # @mention message
        mention_slug = agent_slug if agent.get("ok") else native
        content = f"Hello @{mention_slug} — smoke mention {int(time.time())}"
        code, sent = api(
            "POST",
            f"/api/rooms/{room_id}/messages/send",
            body={"content": content, "invoke_agents": bool(args.live_mention)},
        )
        mentions = sent.get("agent_mentions") or []
        check(
            "mention send",
            code == 200 and sent.get("ok"),
            f"mentions={mentions} err={sent.get('error')}",
        )

        # Reply (thread)
        if sent.get("message_id"):
            code, reply = api(
                "POST",
                f"/api/rooms/{room_id}/messages/send",
                body={
                    "content": "Reply in thread — smoke",
                    "parent_message_id": sent["message_id"],
                    "invoke_agents": False,
                },
            )
            check("reply send", code == 200 and reply.get("ok"), reply.get("error") or "")

    print("---")
    if failures:
        print(f"FAILED ({len(failures)}): {', '.join(failures)}")
        raise SystemExit(1)
    print("dogfood flows smoke: all ok")


if __name__ == "__main__":
    main()
