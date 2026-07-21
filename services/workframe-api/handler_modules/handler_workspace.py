"""Workspace / room / board / content route handlers (WF-032 slice)."""

from __future__ import annotations

import hashlib
import json
import queue
import re
import secrets
import sqlite3
import time
import urllib.parse
import uuid

import activity_feed
import api_errors
import chat_bind
from email_sender import APP_BASE_URL, send_branded_invite_email

list_room_sessions = chat_bind.list_room_sessions
room_activity_data = activity_feed.room_activity_data
room_chat_bind = chat_bind.room_chat_bind
profile_chat_activate_room_session = chat_bind.profile_chat_activate_room_session


def _srv():
    import server

    return server


class WorkspaceRoutesMixin:

    def _route_get_board(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, srv.board_list())

    def _route_get_content(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, srv.content_list())

    def _route_get_content_get(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        rel = qs.get("path", [""])[0]
        reason = srv._workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        fp = srv._safe_content_path(rel)
        if not fp or not fp.is_file():
            self._json(404, {"error": "not found"})
            return
        text = fp.read_text(encoding="utf-8", errors="replace")
        self._json(200, {"path": rel, "content": text, "text": text})

    def _route_pattern_get_files_workspace(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        prefix = "/api/files/workspace/"
        if not path.startswith(prefix):
            self._json(404, {"error": "not found"})
            return
        rel = urllib.parse.unquote(path[len(prefix) :].lstrip("/"))
        reason = srv._workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        try:
            data, mime = srv.file_raw(rel)
        except ValueError:
            self._json(404, {"error": "not found"})
            return
        self._send(200, data, mime)

    def _route_post_board(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        self._json(201, srv.board_create(body))

    def _route_post_board_update(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        qs = getattr(self, "_post_qs", {})
        task_id = qs.get("id", [""])[0]
        if not task_id:
            self._json(400, {"error": "id required"})
            return
        self._json(200, srv.board_update(task_id, body))

    def _route_post_board_delete(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        qs = getattr(self, "_post_qs", {})
        task_id = qs.get("id", [""])[0]
        if not task_id:
            self._json(400, {"error": "id required"})
            return
        srv.board_delete(task_id)
        self._json(200, {"ok": True})

    def _route_post_content_save(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        rel = str(body.get("path") or "").strip()
        reason = srv._workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        content = str(body.get("content") or "")
        fp = srv._safe_content_path(rel)
        if not fp:
            self._json(400, {"error": "invalid path"})
            return
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        srv._bump_workspace_state(fp)
        self._json(200, {"ok": True, "path": rel.replace("\\", "/")})

    def _route_post_content_delete(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        qs = getattr(self, "_post_qs", {})
        rel = qs.get("path", [""])[0] or str(body.get("path") or "")
        reason = srv._workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        fp = srv._safe_content_path(rel)
        if not fp or not fp.is_file():
            self._json(404, {"error": "not found"})
            return
        fp.unlink()
        srv._bump_workspace_state(fp.parent)
        self._json(200, {"ok": True})

    def _route_pattern_get_workspace_rooms(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        include_members = qs.get("include_members", [""])[0].lower() in {"1", "true", "yes"}
        self._json(*srv._list_rooms(ws_id, include_members=include_members))

    def _route_pattern_get_room(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        rid = path.strip("/").split("/")[-1]
        self._json(*srv._get_room(rid))

    def _route_pattern_get_room_members(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        rid = path.strip("/").split("/")[-2]
        viewer_id = str(getattr(self, "auth_user", "") or "")
        try:
            conn = srv._workframe_db()
            conn.row_factory = sqlite3.Row
            if not srv._user_can_access_room(conn, rid, viewer_id):
                conn.close()
                self._json(403, {"ok": False, "error": "forbidden"})
                return
            members = conn.execute(
                "SELECT * FROM room_memberships WHERE room_id = ? AND deleted_at IS NULL",
                (rid,),
            ).fetchall()
            payload = srv._enrich_room_members(conn, [dict(m) for m in members])
            conn.close()
        except Exception:
            payload = []
        self._json(200, {"ok": True, "room_id": rid, "members": payload})

    def _route_pattern_get_room_live(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        rid = path.strip("/").split("/")[-2]
        user_id = str(getattr(self, "auth_user", "") or "")
        try:
            conn = srv._workframe_db()
            if not srv._user_can_access_room(conn, rid, user_id):
                conn.close()
                self._json(403, {"ok": False, "error": "forbidden"})
                return
            conn.close()
        except Exception:
            self._json(500, {"ok": False, "error": "db_error"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        cors_origin = srv._cors_origin_for(self.headers)
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
        self.send_header("Vary", "Origin")
        self.end_headers()
        sub = srv._room_live_subscribe(rid)
        try:
            for turn in srv._room_live_active_for_room(rid):
                payload = json.dumps(turn)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
            while True:
                try:
                    line = sub.get(timeout=15)
                    self.wfile.write(f"data: {line}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    heartbeat = json.dumps(
                        {"type": "heartbeat", "room_id": rid, "ts": int(time.time())}
                    )
                    self.wfile.write(f"data: {heartbeat}\n\n".encode("utf-8"))
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            srv._room_live_unsubscribe(rid, sub)

    def _route_pattern_get_room_activity(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        rid = path.strip("/").split("/")[-2]
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        try:
            activity = srv.room_activity_data(rid, user_id)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        self._json(200, {"ok": True, "room_id": rid, "activity": activity})

    def _route_pattern_get_room_sessions(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        rid = path.strip("/").split("/")[-2]
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        try:
            payload = srv.list_room_sessions(rid, user_id)
        except ValueError as exc:
            err = str(exc)
            if "not_found" in err:
                self._json(404, {"ok": False, "error": err})
                return
            if "denied" in err or "forbidden" in err:
                self._json(403, {"ok": False, "error": err})
                return
            self._json(400, {"ok": False, "error": err})
            return
        self._json(200, payload)

    def _route_pattern_get_room_messages(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        slug_or_id = path.strip("/").split("/")[-2]
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        limit = int(qs.get("limit", ["50"])[0])
        offset = int(qs.get("offset", ["0"])[0])
        try:
            conn = srv._workframe_db()
            room = conn.execute(
                "SELECT id FROM rooms WHERE (id = ? OR slug = ?) AND deleted_at IS NULL",
                (slug_or_id, slug_or_id),
            ).fetchone()
            if not room:
                conn.close()
                self._json(404, {"error": "room_not_found"})
                return
            rid = room["id"]
            if not srv._user_can_access_room(conn, rid, user_id):
                conn.close()
                self._json(403, {"ok": False, "error": "forbidden"})
                return
            messages = conn.execute(
                """
                SELECT * FROM (
                    SELECT * FROM messages
                    WHERE room_id = ? AND deleted_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                ) AS recent
                ORDER BY created_at ASC
                """,
                (rid, limit, offset),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE room_id = ? AND deleted_at IS NULL",
                (rid,),
            ).fetchone()[0]
            payload = srv._enrich_room_messages(conn, messages)
            conn.close()
        except Exception:
            messages = []
            total = 0
            payload = []
        self._json(200, {"ok": True, "messages": payload, "total": total, "limit": limit, "offset": offset})

    def _route_pattern_post_workspace_rooms(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        created_by = str(getattr(self, "auth_user", "") or "")
        if not srv._handler_is_active_workspace_member(self, ws_id):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "workspace_member"})
            return
        status, payload = srv._create_room(ws_id, body, created_by)
        if status == 201:
            self._log_audit("room_created", "room", payload["room"]["id"], f"name={payload['room']['name']}")
        self._json(status, payload)

    def _route_pattern_post_workspace_rooms_create(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) < 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        name = str(body.get("name", "")).strip()
        slug = str(body.get("slug", "") or name.lower().replace(" ", "-")).strip()
        room_type = str(body.get("room_type", "channel")).strip()
        topic = str(body.get("topic", "")).strip()
        agent_id = str(body.get("agent_profile_id", "")).strip()
        if not name:
            self._json(400, {"error": "name required"})
            return
        rid = str(uuid.uuid4())
        now_ts = str(int(time.time()))
        try:
            conn = sqlite3.connect(str(srv.AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.execute(
                "INSERT INTO rooms (id, workspace_id, agent_profile_id, name, slug, topic, room_type, status, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (rid, ws_id, agent_id or None, name, slug, topic, room_type, "active", getattr(self, "auth_user", ""), now_ts, now_ts),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        self._log_audit("room_created", "room", rid, f"name={name}")
        self._json(200, {"ok": True, "room_id": rid})

    def _route_pattern_post_room_members(self, path: str, body: dict) -> None:
        srv = _srv()
        rid = path.strip("/").split("/")[-2]
        actor_id = str(getattr(self, "auth_user", "") or "")
        if not actor_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        user_id_to_add = str(body.get("user_id", "")).strip()
        role = str(body.get("role", "member")).strip()
        if not user_id_to_add:
            self._json(400, {"error": "user_id required"})
            return
        mid = str(uuid.uuid4())
        now_ts = str(int(time.time()))
        try:
            conn = srv._workframe_db()
            if not srv._user_can_manage_room_members(conn, rid, actor_id):
                conn.close()
                self._json(403, {"ok": False, "error": "forbidden"})
                return
            conn.execute(
                "INSERT INTO room_memberships (id, room_id, user_id, role, status, joined_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (mid, rid, user_id_to_add, role, "active", now_ts, now_ts),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        self._log_audit("room_member_added", "room_membership", mid, f"room={rid} user={user_id_to_add}")
        self._json(200, {"ok": True, "membership_id": mid})

    def _route_pattern_post_room_bind(self, path: str, body: dict) -> None:
        srv = _srv()
        rid = path.strip("/").split("/")[-2]
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        try:
            self._json(200, srv.room_chat_bind(rid, body, user_id))
        except (ValueError, OSError) as exc:
            payload = api_errors.public_api_error_payload(exc, context="room_bind")
            status = api_errors.http_status_for_code(str(payload.get("error") or ""))
            self._json(status, {"ok": False, **payload})
        except Exception as exc:  # noqa: BLE001 — urllib.URLError etc.
            payload = api_errors.public_api_error_payload(exc, context="room_bind")
            self._json(500, {"ok": False, **payload})

    def _route_pattern_post_room_sessions_activate(self, path: str, body: dict) -> None:
        srv = _srv()
        rid = path.strip("/").split("/")[-3]
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        session_id = str(body.get("session_id", "")).strip()
        template_prof = str(body.get("profile", "")).strip()
        source_id = str(body.get("source_id") or "ui").strip() or "ui"
        client_id = str(body.get("client_id") or "default").strip() or "default"
        binding_version = srv._binding_version(body.get("binding_version"))
        if not session_id:
            self._json(400, {"error": "session_id required"})
            return
        try:
            payload = srv.profile_chat_activate_room_session(
                rid,
                session_id,
                user_id,
                template_prof,
                source_id=source_id,
                client_id=client_id,
                binding_version=binding_version,
            )
        except ValueError as exc:
            payload = api_errors.public_api_error_payload(exc, context="room_session_activate")
            status = api_errors.http_status_for_code(str(payload.get("error") or ""))
            self._json(status, {"ok": False, **payload})
            return
        self._json(200, payload)

    def _route_pattern_post_room_messages_send(self, path: str, body: dict) -> None:
        srv = _srv()
        slug_or_id = path.strip("/").split("/")[-3]
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        sender_agent = str(body.get("sender_agent_id", "")).strip()
        content = str(body.get("content", "")).strip()
        content_type = str(body.get("content_type") or "text").strip()
        parent_value = body.get("parent_message_id")
        parent_id = str(parent_value).strip() if parent_value else None
        if not content:
            self._json(400, {"error": "content required"})
            return
        try:
            conn = srv._workframe_db()
            room = conn.execute(
                """
                SELECT id, workspace_id, room_type, agent_profile_id
                FROM rooms WHERE (id = ? OR slug = ?) AND deleted_at IS NULL
                """,
                (slug_or_id, slug_or_id),
            ).fetchone()
            if not room:
                conn.close()
                self._json(404, {"error": "room_not_found"})
                return
            rid = str(room["id"])
            workspace_id = str(room["workspace_id"])
            if not srv._user_can_access_room(conn, rid, user_id):
                conn.close()
                self._json(403, {"ok": False, "error": "forbidden"})
                return
            if sender_agent:
                sender_user = ""
                agent_member = conn.execute(
                    """
                    SELECT 1 FROM room_memberships
                    WHERE room_id = ? AND agent_profile_id = ? AND deleted_at IS NULL
                    """,
                    (rid, sender_agent),
                ).fetchone()
                if not agent_member:
                    conn.close()
                    self._json(403, {"ok": False, "error": "agent_not_in_room"})
                    return
            else:
                sender_user = str(body.get("sender_user_id", "") or user_id).strip()
                if sender_user != user_id:
                    conn.close()
                    self._json(403, {"ok": False, "error": "forbidden"})
                    return
            mid = str(uuid.uuid4())
            now_ts = str(int(time.time()))
            conn.execute(
                "INSERT INTO messages (id, room_id, sender_user_id, sender_agent_id, parent_message_id, content, content_type, is_edited, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (mid, rid, sender_user or None, sender_agent or None, parent_id, content, content_type, 0, now_ts, now_ts),
            )
            conn.execute("UPDATE rooms SET updated_at = ? WHERE id = ?", (now_ts, rid))
            mention_meta: dict[str, Any] = {}
            if srv._is_space_room(str(room["room_type"]), room["agent_profile_id"]) and not sender_agent:
                invoke_agents = body.get("invoke_agents", True)
                if isinstance(invoke_agents, str):
                    invoke_agents = invoke_agents.lower() not in ("0", "false", "no")
                mention_meta = srv._process_space_message_mentions(
                    rid,
                    workspace_id,
                    user_id,
                    content,
                    mid,
                    invoke_agents=bool(invoke_agents),
                )
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        self._log_audit("message_sent", "message", mid, f"room={rid}")
        self._json(200, {"ok": True, "message_id": mid, **mention_meta})

    def _route_pattern_patch_room(self, path: str, body: dict) -> None:
        srv = _srv()
        room_patch_match = re.fullmatch(r"/api/rooms/([^/]+)", path)
        if room_patch_match:
            user_id = str(getattr(self, "auth_user", "") or "")
            status, payload = srv._patch_room(room_patch_match.group(1), body, user_id)
            if status == 200:
                self._log_audit(
                    "room_updated",
                    "room",
                    room_patch_match.group(1),
                    f"room={room_patch_match.group(1)}",
                    {"changes": body},
                )
            self._json(status, payload)

    def _route_pattern_delete_room(self, path: str, body: dict) -> None:
        srv = _srv()
        rid = path.strip("/").split("/")[-1]
        try:
            db = srv._workframe_db()
            cur = db.execute(
                "UPDATE rooms SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
                (str(int(time.time())), rid),
            )
            db.commit()
            affected = cur.rowcount
            db.close()
        except Exception:
            self._json(500, {"ok": False, "error": "delete_failed"})
            return
        if not affected:
            self._json(404, {"ok": False, "error": "room_not_found"})
            return
        self._log_audit("room_deleted", "room", rid, f"room={rid}")
        self._json(200, {"ok": True, "room_id": rid, "status": "deleted"})

    def _route_pattern_get_workspace(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        match = re.fullmatch(r"/api/workspace/([^/]+)", path)
        if not match:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        user_id = str(getattr(self, "auth_user", "") or "")
        ws_id = srv._resolve_wid(match.group(1))
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        self._json(*srv._get_workspace(ws_id, user_id))

    def _route_pattern_get_workspace_members(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        self._json(*srv._list_workspace_members(ws_id, self))

    def _route_pattern_get_workspace_activity(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        wid = srv._resolve_wid(parts[2])
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        if not wid:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            activity = srv.workspace_activity_data(wid, user_id)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        self._json(200, {"ok": True, "workspace_id": wid, "activity": activity})

    def _route_pattern_get_workspace_kanban_tasks(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 5:
            self._json(404, {"error": "not_found"})
            return
        wid = srv._resolve_wid(parts[2])
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        if not wid:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            payload = srv.kanban_proxy_list_tasks(wid, user_id)
        except PermissionError as exc:
            self._json(403, {"ok": False, "error": str(exc)})
            return
        self._json(200, payload)

    def _route_pattern_get_workspace_delegation_grants(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        wid = srv._resolve_wid(parts[2])
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        if not wid:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            payload = srv.list_delegation_grants(wid, user_id)
        except PermissionError as exc:
            self._json(403, {"ok": False, "error": str(exc)})
            return
        self._json(200, payload)

    def _route_pattern_get_workspace_invites(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        wid = parts[2]
        ws_id = srv._resolve_wid(wid)
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            conn = sqlite3.connect(str(srv.AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            invites = conn.execute(
                "SELECT id, workspace_id, email, role, invited_by_user_id, expires_at, created_at, accepted_at, deleted_at FROM workspace_invites WHERE workspace_id = ? AND deleted_at IS NULL ORDER BY created_at DESC",
                (ws_id,)).fetchall()
            conn.close()
        except Exception:
            invites = []
        self._json(200, {"ok": True, "invites": [dict(i) for i in invites]})

    def _route_pattern_get_invite(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 3:
            self._json(404, {"error": "not_found"})
            return
        token = parts[2]
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        try:
            conn = sqlite3.connect(str(srv.AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            inv = conn.execute(
                "SELECT id, workspace_id, email, role, invited_by_user_id, expires_at, created_at, accepted_at, deleted_at FROM workspace_invites WHERE token_hash = ? AND deleted_at IS NULL",
                (token_hash,)).fetchone()
            conn.close()
        except Exception:
            inv = None
        if not inv:
            self._json(404, {"ok": False, "error": "invite_not_found"})
            return
        self._json(200, {"ok": True, "invite": dict(inv)})

    def _route_pattern_get_workspace_memory(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        wid = parts[2]
        ws_id = srv._resolve_wid(wid)
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            conn = sqlite3.connect(str(srv.AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            items = conn.execute(
                "SELECT * FROM memory_items WHERE workspace_id = ? AND deleted_at IS NULL ORDER BY created_at DESC",
                (ws_id,)).fetchall()
            conn.close()
        except Exception:
            items = []
        self._json(200, {"ok": True, "items": [dict(i) for i in items]})

    def _route_pattern_get_workspace_budget(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            conn = sqlite3.connect(str(srv.AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            policies = conn.execute(
                "SELECT * FROM budget_policies WHERE workspace_id = ? ORDER BY created_at DESC",
                (ws_id,)).fetchall()
            conn.close()
        except Exception:
            policies = []
        self._json(200, {"ok": True, "budget_policies": [dict(p) for p in policies]})

    def _route_pattern_get_workspace_grants(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            conn = sqlite3.connect(str(srv.AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            grants = conn.execute(
                "SELECT cg.*, cb.provider AS binding_provider FROM credential_grants cg LEFT JOIN credential_bindings cb ON cb.id = cg.credential_binding_id WHERE cb.workspace_id = ? OR cg.grantee_id = ? ORDER BY cg.created_at DESC",
                (ws_id, ws_id)).fetchall()
            conn.close()
        except Exception:
            grants = []
        self._json(200, {"ok": True, "grants": [dict(g) for g in grants]})

    def _route_pattern_get_workspace_events(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) < 4:
            self._json(404, {"error": "not_found"})
            return
        wid = parts[2]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        cors_origin = srv._cors_origin_for(self.headers)
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
        self.send_header("Vary", "Origin")
        self.end_headers()
        last_revision = ""
        last_heartbeat = time.time()
        try:
            while True:
                try:
                    conn = srv._workframe_db()
                    revision = srv._workspace_sse_revision(conn, wid)
                    conn.close()
                except Exception:
                    revision = "error"
                if revision != last_revision:
                    payload = json.dumps(srv._workspace_event_payload(wid, revision))
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    last_revision = revision
                    last_heartbeat = time.time()
                elif time.time() - last_heartbeat >= 15:
                    heartbeat = json.dumps({"type": "heartbeat", "workspace_id": wid, "ts": int(time.time())})
                    self.wfile.write(f"data: {heartbeat}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    last_heartbeat = time.time()
                time.sleep(1)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _route_pattern_get_workspace_credentials(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        try:
            conn = sqlite3.connect(str(srv._workframe_db_path()), timeout=3.0)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT id, workspace_id, user_id, agent_profile_id, provider,
                          credential_type, credential_ref, label, is_active,
                          expires_at, created_by, created_at, updated_at
                   FROM credential_bindings
                   WHERE workspace_id = ? AND deleted_at IS NULL
                   ORDER BY created_at DESC""",
                (ws_id,),
            ).fetchall()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"ok": False, "error": str(exc)})
            return
        self._json(200, {
            "ok": True,
            "scope": "workspace",
            "workspace_id": ws_id,
            "credentials": [dict(r) for r in rows],
        })

    def _route_pattern_post_workspace_credentials_store(self, path: str, body: dict) -> None:
        srv = _srv()
        # POST /api/workspace/:wid/credentials/store
        parts = path.strip("/").split("/")
        if len(parts) < 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        provider = str(body.get("provider", "")).strip().lower()
        api_key = str(body.get("api_key", "") or body.get("secret", "")).strip()
        label = str(body.get("label", "") or provider)
        if not provider or not api_key:
            self._json(400, {"error": "provider and api_key required"})
            return
        spec = srv._catalog_provider(provider)
        if not spec:
            self._json(400, {"error": "provider_not_found"})
            return
        if spec.get("user_only"):
            self._json(403, {"ok": False, "error": "provider_user_only"})
            return
        env_var = str(spec.get("env_var") or srv._default_credential_env_var(provider, "api_key"))
        try:
            payload = srv._store_workspace_credential(
                ws_id,
                provider,
                "api_key",
                api_key,
                env_var,
                label,
                str(getattr(self, "auth_user", "") or ""),
            )
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        cred_id = str(payload["credential_id"])
        srv._revoke_runtime_llm_leases(workspace_id=ws_id, provider=provider)
        self._log_audit("credential_stored", "credential_binding", cred_id, f"provider={provider}")
        try:
            srv._bootstrap_model_after_llm_connect("", ws_id, provider)
        except (OSError, RuntimeError, ValueError) as exc:
            srv._log_handler_error("POST workspace credentials/store bootstrap", exc)
        if str(spec.get("category") or "") == "messaging":
            sync_result = srv._sync_workspace_messaging_gateway(ws_id)
            if not sync_result.get("ok"):
                self._json(500, {"ok": False, "error": sync_result.get("error") or "messaging_sync_failed"})
                return
        self._json(200, {"ok": True, "credential_id": cred_id, "credential_ref": payload["credential_ref"]})

    def _route_pattern_post_workspace_credentials_revoke(self, path: str, body: dict) -> None:
        srv = _srv()
        # POST /api/workspace/:wid/credentials/:bindingId/revoke
        parts = path.strip("/").split("/")
        if len(parts) < 5:
            self._json(404, {"error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        binding_id = parts[4]
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        try:
            conn = sqlite3.connect(str(srv.AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT provider FROM credential_bindings WHERE id = ? AND workspace_id = ?",
                (binding_id, ws_id),
            ).fetchone()
            provider = str(row["provider"] or "").strip().lower() if row else ""
            cur = conn.execute(
                "UPDATE credential_bindings SET is_active = 0, updated_at = ? WHERE id = ? AND workspace_id = ?",
                (str(int(time.time())), binding_id, ws_id),
            )
            conn.commit()
            affected = cur.rowcount
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        if not affected:
            self._json(404, {"error": "credential_not_found"})
            return
        srv._revoke_runtime_llm_leases(
            workspace_id=ws_id,
            provider=provider,
            credential_binding_id=binding_id,
        )
        self._log_audit("credential_revoked", "credential_binding", binding_id, f"workspace={ws_id}")
        spec = srv._catalog_provider(provider)
        if spec and str(spec.get("category") or "") == "messaging":
            sync_result = srv._sync_workspace_messaging_gateway(ws_id)
            if not sync_result.get("ok"):
                self._json(500, {"ok": False, "error": sync_result.get("error") or "messaging_sync_failed"})
                return
        self._json(200, {"ok": True, "credential_id": binding_id, "status": "revoked"})

    def _route_pattern_post_workspace_invites(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        email = str(body.get("email", "")).strip()
        role = str(body.get("role", "member")).strip()
        if not email:
            self._json(400, {"error": "email required"})
            return
        invite_id = str(uuid.uuid4())
        token = secrets.token_hex(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now_ts = str(int(time.time()))
        expires_at = str(int(time.time()) + 86400 * 7)
        try:
            conn = sqlite3.connect(str(srv.AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.execute(
                "INSERT INTO workspace_invites (id, workspace_id, email, role, token_hash, invited_by_user_id, expires_at, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (invite_id, ws_id, email, role, token_hash, getattr(self, "auth_user", ""), expires_at, now_ts),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        invite_url = f"{APP_BASE_URL}/?invite_token={urllib.parse.quote(token)}&email={urllib.parse.quote(email)}"
        email_sent = False
        email_error = None
        ws_name = ws_id
        logo_url = ""
        try:
            conn = sqlite3.connect(str(srv._workframe_db_path()), timeout=3.0)
            conn.row_factory = sqlite3.Row
            ws_row = conn.execute(
                "SELECT display_name, avatar_url FROM workspaces WHERE id = ?",
                (ws_id,),
            ).fetchone()
            conn.close()
            if ws_row:
                ws_name = str(ws_row["display_name"] or ws_id)
                logo_url = str(ws_row["avatar_url"] or "")
        except sqlite3.Error:
            pass
        try:
            send_branded_invite_email(email, ws_name, invite_url, logo_url)
            email_sent = True
        except Exception as exc:
            email_error = str(exc)
        self._log_audit("invite_created", "workspace_invite", invite_id, f"workspace={ws_id} email={email}")
        payload = {"ok": True, "invite_id": invite_id, "token": token, "email": email, "role": role, "expires_at": expires_at, "invite_url": invite_url, "email_sent": email_sent}
        if email_error:
            payload["email_error"] = email_error
        self._json(201, payload)

    def _route_pattern_post_invites_accept(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4 or parts[3] != "accept":
            self._json(404, {"error": "not_found"})
            return
        token = parts[2]
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            if srv.DEV_LOCAL_UNSAFE:
                user_id = "dev"
            else:
                self._json(401, {"ok": False, "error": "no_authenticated_user"})
                return
        try:
            conn = sqlite3.connect(str(srv.AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            inv = conn.execute(
                "SELECT * FROM workspace_invites WHERE token_hash = ? AND deleted_at IS NULL AND accepted_at IS NULL",
                (token_hash,)).fetchone()
            if not inv:
                conn.close()
                self._json(404, {"ok": False, "error": "invite_not_found_or_expired"})
                return
            invite_email = str(inv["email"] or "").strip().lower()
            user_row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
            user_email = str(user_row["email"] or "").strip().lower() if user_row else ""
            if not user_email or user_email != invite_email:
                conn.close()
                self._json(403, {"ok": False, "error": "invite_email_mismatch"})
                return
            if int(inv["expires_at"]) < int(time.time()):
                conn.close()
                self._json(410, {"ok": False, "error": "invite_expired"})
                return
            wid = inv["workspace_id"]
            role = inv["role"]
            membership_id = str(uuid.uuid4())
            now_ts = str(int(time.time()))
            inviter_id = str(inv["invited_by_user_id"] or "").strip()
            existing = conn.execute(
                "SELECT id FROM workspace_memberships WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL",
                (wid, user_id)).fetchone()
            if existing:
                room_join = srv._onboard_workspace_member_rooms(
                    conn,
                    wid,
                    user_id,
                    inviter_user_id=inviter_id or None,
                )
                dm_room = srv._ensure_user_dm_room(conn, wid, user_id, inviter_id)
                conn.execute("UPDATE workspace_invites SET accepted_by_user_id = ?, accepted_at = ?, deleted_at = ? WHERE id = ?",
                             (user_id, now_ts, now_ts, inv["id"]))
                conn.commit()
                conn.close()
                # Re-acceptance is also a repair path.  Do not leave an existing
                # member without the per-user Hermes proxy runtimes.
                try:
                    if not srv._provision_invited_member_agent_runtimes(wid, user_id):
                        self._json(500, {"ok": False, "error": "runtime_provision_failed"})
                        return
                except Exception as exc:  # noqa: BLE001
                    self._json(500, {"ok": False, "error": f"runtime_provision_failed: {exc}"})
                    return
                srv._set_user_current_workspace(user_id, wid)
                self._json(200, {"ok": True, "already_member": True, "workspace_id": wid, "room": room_join, "dm_room": dm_room})
                return
            conn.execute(
                "INSERT INTO workspace_memberships (id, workspace_id, user_id, role, status, invited_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (membership_id, wid, user_id, role, "active", inv["invited_by_user_id"], now_ts, now_ts),
            )
            room_join = srv._onboard_workspace_member_rooms(
                conn,
                wid,
                user_id,
                inviter_user_id=inviter_id or None,
            )
            dm_room = srv._ensure_user_dm_room(conn, wid, user_id, inviter_id)
            conn.execute("UPDATE workspace_invites SET accepted_by_user_id = ?, accepted_at = ?, deleted_at = ? WHERE id = ?",
                         (user_id, now_ts, now_ts, inv["id"]))
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        if not srv._provision_invited_member_agent_runtimes(wid, user_id):
            self._json(500, {"ok": False, "error": "runtime_provision_failed"})
            return
        srv._set_user_current_workspace(user_id, wid)
        self._log_audit("invite_accepted", "workspace_invite", inv["id"], f"workspace={wid} user={user_id}")
        self._json(
            200,
            {
                "ok": True,
                "workspace_id": wid,
                "role": role,
                "membership_id": membership_id,
                "room": room_join,
                "dm_room": dm_room,
            },
        )

    def _route_pattern_post_workspace_members(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        target_user_id = str(body.get("user_id", "") or body.get("email", "")).strip()
        role = str(body.get("role", "member")).strip()
        if not target_user_id:
            self._json(400, {"ok": False, "error": "user_id required"})
            return
        # Check if membership already exists
        try:
            db = srv._workframe_db()
            existing = db.execute("SELECT id FROM workspace_memberships WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL", (ws_id, target_user_id)).fetchone()
            db.close()
        except Exception:
            existing = None
        if existing:
            # Update existing membership
            status, payload = srv._patch_workspace_members(ws_id, {"user_id": target_user_id, "role": role}, self)
        else:
            # Create new membership
            mid = str(uuid.uuid4())
            now_ts = str(int(time.time()))
            try:
                db = srv._workframe_db()
                db.execute("INSERT INTO workspace_memberships (id, workspace_id, user_id, role, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)", (mid, ws_id, target_user_id, role, "active", now_ts, now_ts))
                srv._onboard_workspace_member_rooms(db, ws_id, target_user_id)
                db.commit()
                db.close()
                status, payload = 200, {"ok": True, "membership_id": mid, "user_id": target_user_id, "role": role}
            except sqlite3.Error as exc:
                status, payload = 500, {"ok": False, "error": str(exc)}
        if status == 200:
            self._log_audit("workspace_member_added", "workspace_membership", f"{ws_id}/{target_user_id}", f"workspace={ws_id} user={target_user_id}")
        self._json(status, payload)

    def _route_pattern_post_workspace_kanban_tasks(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 5:
            self._json(404, {"error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            payload = srv.kanban_proxy_create_task(ws_id, user_id, body)
        except PermissionError as exc:
            self._json(403, {"ok": False, "error": str(exc)})
            return
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        self._json(201, payload)

    def _route_pattern_post_workspace_delegation_grants(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        grantee_user_id = str(body.get("grantee_user_id") or "").strip()
        scope = str(body.get("scope") or srv.DELEGATION_SCOPE_AGENTS_DELEGATE).strip()
        try:
            payload = srv.create_delegation_grant(ws_id, user_id, grantee_user_id, scope=scope)
        except PermissionError as exc:
            self._json(403, {"ok": False, "error": str(exc)})
            return
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        self._json(201, payload)

    def _route_pattern_post_workspace_runtime_profiles_purge(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 5:
            self._json(404, {"error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        conn = srv._workframe_db()
        try:
            role = srv._workspace_member_role(conn, ws_id, user_id)
        finally:
            conn.close()
        if role not in srv.OWNER_ADMIN_ROLES:
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        try:
            payload = srv.purge_stale_runtime_profiles(ws_id)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        self._json(200, payload)

    def _route_pattern_post_workspace_memory(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        content = str(body.get("content", "")).strip()
        if not content:
            self._json(400, {"error": "content required"})
            return
        agent_profile_id = str(body.get("agent_profile_id", "") or None)
        scope = str(body.get("scope", "workspace")).strip()
        room_id = str(body.get("room_id") or None) if body.get("room_id") else None
        user_id_mem = str(body.get("user_id") or None) if body.get("user_id") else None
        visibility = str(body.get("visibility", "shared")).strip()
        mem_id = str(uuid.uuid4())
        now_ts = str(int(time.time()))
        try:
            conn = sqlite3.connect(str(srv.AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.execute(
                "INSERT INTO memory_items (id, workspace_id, agent_profile_id, scope, room_id, user_id, content, visibility, created_by_user_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (mem_id, ws_id, agent_profile_id, scope, room_id, user_id_mem, content, visibility, getattr(self, "auth_user", ""), now_ts, now_ts),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        self._log_audit("memory_created", "memory_item", mem_id, f"workspace={ws_id} scope={scope}")
        self._json(201, {"ok": True, "memory_id": mem_id})

    def _route_pattern_post_workspace_budget(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        subject_type = str(body.get("subject_type", "workspace")).strip()
        subject_id = str(body.get("subject_id") or ws_id)
        provider = str(body.get("provider", "") or None)
        daily_limit = body.get("daily_limit_cents")
        monthly_limit = body.get("monthly_limit_cents")
        allowed_models = str(body.get("allowed_models", "") or None)
        now_ts = str(int(time.time()))
        policy_id = str(uuid.uuid4())
        try:
            conn = sqlite3.connect(str(srv.AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.execute(
                "INSERT INTO budget_policies (id, workspace_id, subject_type, subject_id, provider, daily_limit_cents, monthly_limit_cents, allowed_models, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (policy_id, ws_id, subject_type, subject_id, provider, daily_limit, monthly_limit, allowed_models, now_ts, now_ts),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        self._log_audit("budget_created", "budget_policy", policy_id, f"workspace={ws_id} subject={subject_type}")
        self._json(201, {"ok": True, "budget_policy_id": policy_id})

    def _route_pattern_post_workspace_grants(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        credential_binding_id = str(body.get("credential_binding_id", "")).strip()
        if not credential_binding_id:
            self._json(400, {"error": "credential_binding_id required"})
            return
        grantee_type = str(body.get("grantee_type", "user")).strip()
        grantee_id = str(body.get("grantee_id", "")).strip()
        if not grantee_id:
            self._json(400, {"error": "grantee_id required"})
            return
        provider = str(body.get("provider", "") or None)
        max_daily = body.get("max_daily_cents")
        max_total = body.get("max_total_cents")
        allowed_models = str(body.get("allowed_models", "") or None)
        allowed_agent_ids = str(body.get("allowed_agent_profile_ids", "") or None)
        allowed_room_ids = str(body.get("allowed_room_ids", "") or None)
        expires_at = str(body.get("expires_at") or None) if body.get("expires_at") else None
        grant_id = str(uuid.uuid4())
        now_ts = str(int(time.time()))
        user_id = str(getattr(self, "auth_user", "") or "")
        try:
            conn = sqlite3.connect(str(srv.AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.execute(
                "INSERT INTO credential_grants (id, credential_binding_id, granted_by_user_id, grantee_type, grantee_id, provider, max_daily_cents, max_total_cents, allowed_models, allowed_agent_profile_ids, allowed_room_ids, expires_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (grant_id, credential_binding_id, user_id, grantee_type, grantee_id, provider, max_daily, max_total, allowed_models, allowed_agent_ids, allowed_room_ids, expires_at, now_ts),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        self._log_audit("grant_created", "credential_grant", grant_id, f"workspace={ws_id} grantee={grantee_type}:{grantee_id}")
        self._json(201, {"ok": True, "grant_id": grant_id})

    def _route_pattern_patch_workspace_members(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"ok": False, "error": "not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        status, payload = srv._patch_workspace_members(ws_id, body, self)
        if status == 200:
            self._log_audit(
                "workspace_member_updated",
                "workspace_membership",
                ws_id,
                f"workspace={ws_id}",
                {"workspace_id": ws_id, "changes": body},
            )
        self._json(status, payload)

    def _route_pattern_patch_workspace_integrations(self, path: str, body: dict) -> None:
        srv = _srv()
        workspace_integrations_match = re.fullmatch(r"/api/workspace/([^/]+)/integrations", path)
        if workspace_integrations_match:
            user_id = str(getattr(self, "auth_user", "") or "")
            ws_id = srv._resolve_wid(workspace_integrations_match.group(1))
            if not ws_id:
                self._json(404, {"ok": False, "error": "workspace_not_found"})
                return
            status, payload = srv._patch_workspace_integrations(ws_id, body, user_id)
            if status == 200:
                self._log_audit(
                    "workspace_integrations_updated",
                    "workspace",
                    ws_id,
                    f"workspace={ws_id}",
                    {"changes": list(body.keys())},
                )
            self._json(status, payload)

    def _route_pattern_patch_workspace(self, path: str, body: dict) -> None:
        srv = _srv()
        workspace_patch_match = re.fullmatch(r"/api/workspace/([^/]+)", path)
        if workspace_patch_match:
            user_id = str(getattr(self, "auth_user", "") or "")
            ws_id = srv._resolve_wid(workspace_patch_match.group(1))
            if not ws_id:
                self._json(404, {"ok": False, "error": "workspace_not_found"})
                return
            status, payload = srv._patch_workspace(ws_id, body, user_id)
            if status == 200:
                self._log_audit(
                    "workspace_updated",
                    "workspace",
                    ws_id,
                    f"workspace={ws_id}",
                    {"changes": body},
                )
            self._json(status, payload)

    def _route_pattern_delete_workspace_members(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        ws_id = srv._resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        target_user_id = str(body.get("user_id", "")).strip()
        if not target_user_id:
            self._json(400, {"ok": False, "error": "user_id required"})
            return
        try:
            db = srv._workframe_db()
            cur = db.execute(
                "UPDATE workspace_memberships SET deleted_at = ?, status = 'removed' WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL",
                (str(int(time.time())), ws_id, target_user_id),
            )
            db.commit()
            affected = cur.rowcount
            db.close()
        except Exception:
            self._json(500, {"ok": False, "error": "delete_failed"})
            return
        if not affected:
            self._json(404, {"ok": False, "error": "member_not_found"})
            return
        self._log_audit(
            "workspace_member_removed",
            "workspace_membership",
            f"{ws_id}/{target_user_id}",
            f"workspace={ws_id} user={target_user_id}",
        )
        self._json(200, {"ok": True, "user_id": target_user_id, "status": "removed"})
