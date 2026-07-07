"""WF-032 extract: activity feed aggregation (Hermes + run ledger)."""
from __future__ import annotations

import json
import sqlite3
from typing import Any
from urllib.parse import urlparse

import run_ledger


ACTIVITY_ROOM_LIMIT = 250
ACTIVITY_WORKSPACE_LIMIT = 1000


def _srv():
    import server as srv

    return srv


def _crew_lookup(crew: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for member in crew:
        for alias in (
            member.get("profile"),
            member.get("key"),
            member.get("display_name"),
            str(member.get("display_name", "")).lower(),
        ):
            if alias:
                lookup[str(alias).lower()] = member
    return lookup


def _resolve_agent(member: dict[str, Any] | None, fallback: str) -> dict[str, str]:
    if member:
        return {
            "agent_name": member["display_name"],
            "profile": member["profile"],
            "key": member["key"],
        }
    slug = fallback.lower()
    return {"agent_name": fallback, "profile": fallback, "key": slug}


def _message_activity(profile: str, crew_lookup: dict[str, Any], limit: int = 80) -> list[dict[str, Any]]:
    """Extract individual tool calls from messages table as atomic activity entries."""
    db = _srv()._profile_dir(profile) / "state.db"
    conn = _srv()._ro_sqlite_live(db)
    if not conn:
        return []
    entries: list[dict[str, Any]] = []
    member = crew_lookup.get(profile.lower()) or crew_lookup.get(_srv()._profile_slug(profile).lower())
    agent = _resolve_agent(member, _srv()._profile_display_name(profile))

    try:
        open_sessions = {
            str(row["id"])
            for row in conn.execute("SELECT id FROM sessions WHERE ended_at IS NULL").fetchall()
        }
        completed_tools = {
            str(row["tool_call_id"])
            for row in conn.execute(
                """
                SELECT tool_call_id FROM messages
                WHERE role = 'tool' AND tool_call_id IS NOT NULL AND tool_call_id != ''
                """,
            ).fetchall()
        }

        rows = conn.execute(
            """
            SELECT m.id, m.session_id, m.timestamp, m.token_count, m.content, m.tool_calls,
                   m.tool_name, s.model
            FROM messages m
            LEFT JOIN sessions s ON s.id = m.session_id
            WHERE m.role = 'assistant'
              AND m.tool_calls IS NOT NULL
              AND m.tool_calls != '[]'
            ORDER BY m.timestamp DESC
            LIMIT ?
            """,
            (limit * 3,),
        ).fetchall()

        for r in rows:
            timestamp = r["timestamp"]
            tool_calls_raw = r["tool_calls"]
            session_id = str(r["session_id"] or "")

            parsed_calls: list[dict[str, Any]] = []
            try:
                parsed_calls = json.loads(tool_calls_raw) if tool_calls_raw else []
            except (json.JSONDecodeError, TypeError):
                continue

            if not parsed_calls:
                continue

            model = r["model"] or ""

            for tc in parsed_calls:
                fn = tc.get("function") or {}
                tool_name = fn.get("name") or tc.get("tool_name") or "unknown"
                raw_args = fn.get("arguments") or tc.get("arguments") or "{}"

                args: dict[str, Any] = {}
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except (json.JSONDecodeError, TypeError):
                    pass

                label = _tool_call_label(tool_name, args)
                call_id = str(tc.get("id") or tc.get("call_id") or "")
                has_result = call_id in completed_tools
                session_open = session_id in open_sessions
                if has_result:
                    status = "completed"
                elif session_open:
                    status = "active"
                else:
                    status = "idle"
                summary = f"running tool: {tool_name}" if status == "active" else f"tool: {tool_name}"

                entries.append({
                    "id": f"tool:{profile}:{call_id or r['id']}:{tool_name}",
                    "kind": "tool_call",
                    "agent_name": agent["agent_name"],
                    "profile": agent["profile"],
                    "key": agent["key"],
                    "task_description": summary,
                    "status": status,
                    "model_used": model,
                    "created_at": _srv()._iso_from_unix(timestamp),
                    "source": "message",
                    "tool_call_id": call_id,
                    "message_id": r["id"],
                    "session_id": session_id,
                    "token_count": r["token_count"] or 0,
                    "tool_name": tool_name,
                })

                if len(entries) >= limit:
                    break

            if len(entries) >= limit:
                break

    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return entries


def _tool_call_label(tool_name: str, args: dict[str, Any]) -> str:
    """Build a short, human-readable label for a tool call."""
    name_lower = tool_name.lower()

    if name_lower == "read_file":
        path = args.get("path", "") or args.get("file_path", "")
        if path:
            short = str(path).split("/")[-1]
            return f"read {short}"
        return "read_file"

    if name_lower == "write_file":
        path = args.get("path", "") or args.get("file_path", "")
        if path:
            short = str(path).split("/")[-1]
            return f"write {short}"
        return "write_file"

    if name_lower == "terminal":
        cmd = args.get("command", "") or args.get("cmd", "")
        if cmd:
            cmd_str = str(cmd).strip()
            if len(cmd_str) > 40:
                return f"terminal: {cmd_str[:37]}â€¦"
            return f"terminal: {cmd_str}"
        return "terminal"

    if name_lower in ("web_search", "search"):
        query = args.get("query", "")
        if query:
            q = str(query).strip()
            if len(q) > 35:
                return f"search: {q[:32]}â€¦"
            return f"search: {q}"
        return "search"

    if name_lower == "skill_view":
        skill = args.get("name", "")
        if skill:
            return f"load skill: {skill}"
        return "skill_view"

    if name_lower == "browser_navigate":
        url = args.get("url", "")
        if url:
            parsed = urlparse(str(url))
            host = parsed.netloc or str(url)
            if len(host) > 30:
                return f"browser: {host[:27]}â€¦"
            return f"browser: {host}"
        return "browser"

    if name_lower in ("delegate_task", "subagent"):
        goal = args.get("goal", "") or args.get("task", "")
        if goal:
            g = str(goal).strip()
            if len(g) > 35:
                return f"delegate: {g[:32]}â€¦"
            return f"delegate: {g}"
        return "delegate"

    if name_lower == "memory":
        action = args.get("action", "")
        if action:
            return f"memory: {action}"
        return "memory"

    # Generic fallback: tool_name + first arg value
    if args:
        first_key = next(iter(args))
        first_val = str(args[first_key])
        if len(first_val) > 30:
            first_val = first_val[:27] + "â€¦"
        return f"{tool_name}: {first_val}"

    return tool_name


def _activity_default_peer_handle() -> str:
    """Best-effort @handle for activity session subtitles."""
    try:
        conn = sqlite3.connect(str(_srv()._workframe_db_path()), timeout=2.0)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT display_name, email FROM users WHERE deleted_at IS NULL ORDER BY created_at ASC LIMIT 1",
        ).fetchone()
        conn.close()
        if row:
            handle = _srv()._mention_handle(str(row["display_name"] or ""), str(row["email"] or ""))
            if handle:
                return handle
    except (sqlite3.Error, OSError):
        pass
    return "user"


def _session_activity_label(
    conn: sqlite3.Connection,
    profile: str,
    session_id: str,
    title: str,
    msg_count: int,
    model: str,
) -> str:
    del conn, profile, session_id, title, msg_count, model  # ponytail: uniform label, not message dumps
    return f"chatting with @{_activity_default_peer_handle()}"


def _session_activity(profile: str, crew_lookup: dict[str, dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    db = _srv()._profile_dir(profile) / "state.db"
    conn = _srv()._ro_sqlite_live(db)
    if not conn:
        return []
    entries: list[dict[str, Any]] = []
    member = crew_lookup.get(profile.lower()) or crew_lookup.get(_srv()._profile_slug(profile).lower())
    agent = _resolve_agent(member, _srv()._profile_display_name(profile))
    try:
        rows = conn.execute(
            """
            SELECT id, source, title, started_at, ended_at, message_count, model
            FROM sessions
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        for r in rows:
            session_id = str(r["id"] or "")
            ended = r["ended_at"]
            msg_count = int(r["message_count"] or 0)
            model = str(r["model"] or "").strip()
            title = (r["title"] or "").strip()
            desc = _session_activity_label(conn, profile, session_id, title, msg_count, model)
            if len(desc) > 140:
                desc = desc[:137] + "..."
            status = "completed" if ended else "idle"
            entries.append(
                {
                    "id": f"session:{profile}:{session_id}",
                    "kind": "session_start",
                    "agent_name": agent["agent_name"],
                    "profile": agent["profile"],
                    "key": agent["key"],
                    "task_description": desc,
                    "status": status,
                    "model_used": model,
                    "created_at": _srv()._iso_from_unix(r["started_at"]),
                    "source": "session",
                    "session_id": session_id,
                    "message_count": msg_count,
                }
            )
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return entries


def _kanban_activity(
    crew_lookup: dict[str, dict[str, Any]],
    limit: int = 50,
    board_slug: str = "default",
) -> list[dict[str, Any]]:
    db = _srv()._hermes_kanban_db_path(board_slug)
    conn = _srv()._ro_sqlite_live(db)
    if not conn:
        return []
    entries: list[dict[str, Any]] = []
    try:
        rows = conn.execute(
            """
            SELECT e.kind, e.created_at, t.title, t.assignee, t.status
            FROM task_events e
            JOIN tasks t ON t.id = e.task_id
            ORDER BY e.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        for r in rows:
            assignee = str(r["assignee"] or "kanban")
            member = crew_lookup.get(assignee.lower()) or crew_lookup.get(_srv()._profile_slug(assignee).lower())
            agent = _resolve_agent(member, _srv()._profile_display_name(assignee) if assignee != "kanban" else "Kanban")
            desc = f"{r['title'] or 'task'} Â· {r['kind']}"
            if len(desc) > 140:
                desc = desc[:137] + "..."
            st = str(r["status"] or r["kind"] or "event").lower()
            if st in ("done", "completed"):
                status = "completed"
            elif "fail" in st or st == "blocked":
                status = "failed"
            else:
                status = st
            entries.append(
                {
                    "id": f"kanban:{assignee}:{r['created_at']}:{r['kind']}",
                    "kind": "kanban_task",
                    "agent_name": agent["agent_name"],
                    "profile": agent["profile"],
                    "key": agent["key"],
                    "task_description": desc,
                    "status": status,
                    "model_used": "",
                    "created_at": _srv()._iso_from_unix(r["created_at"]),
                    "source": "kanban",
                }
            )
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return entries


def activity_data(profiles: list[str], crew: list[dict[str, Any]]) -> dict[str, Any]:
    crew_lookup = _crew_lookup(crew)
    merged: list[dict[str, Any]] = []
    for p in profiles:
        merged.extend(_session_activity(p, crew_lookup, 40))
        merged.extend(_message_activity(p, crew_lookup, 60))
    merged.extend(_kanban_activity(crew_lookup, 40))
    merged.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    merged = merged[:80]

    agents: dict[str, dict[str, Any]] = {}
    for e in merged:
        key = str(e.get("key") or e.get("agent_name") or "unknown").lower()
        member = crew_lookup.get(key)
        a = agents.setdefault(
            key,
            {
                "name": e.get("agent_name") or key,
                "display_name": e.get("agent_name") or key,
                "profile": e.get("profile") or key,
                "key": key,
                "total": 0,
                "completed": 0,
                "failed": 0,
                "last_task": "",
                "last_status": "idle",
                "last_seen": "",
                "model": e.get("model_used") or "",
                "role": member.get("role") if member else "",
                "platform": member.get("platform") if member else "Hermes",
                "color": member.get("color") if member else "",
            },
        )
        a["total"] += 1
        st = str(e.get("status") or "").lower()
        if "fail" in st or st == "blocked":
            a["failed"] += 1
        elif st in ("completed", "done", "active"):
            a["completed"] += 1
        if not a["last_task"]:
            a["last_task"] = e.get("task_description") or ""
            a["last_status"] = e.get("status") or ""
            a["last_seen"] = e.get("created_at") or ""
            if e.get("model_used"):
                a["model"] = e["model_used"]

    for member in crew:
        key = member["key"]
        agents.setdefault(
            key,
            {
                "name": member["display_name"],
                "display_name": member["display_name"],
                "profile": member["profile"],
                "key": key,
                "total": 0,
                "completed": 0,
                "failed": 0,
                "last_task": "No activity yet",
                "last_status": "idle",
                "last_seen": "",
                "model": "",
                "role": member.get("role") or "",
                "platform": member.get("platform") or "Hermes",
                "color": member.get("color") or "",
            },
        )

    by_day: dict[str, dict[str, Any]] = {}
    for e in merged:
        day = str(e.get("created_at") or "")[:10]
        if not day:
            continue
        slot = by_day.setdefault(day, {"day": day, "total": 0, "agents": {}})
        slot["total"] += 1
        an = str(e.get("key") or e.get("agent_name") or "unknown").lower()
        slot["agents"][an] = slot["agents"].get(an, 0) + 1

    total = len(merged)
    completed = sum(
        1 for e in merged if str(e.get("status", "")).lower() in ("completed", "done", "active")
    )
    failed = sum(
        1
        for e in merged
        if "fail" in str(e.get("status", "")).lower() or str(e.get("status", "")).lower() == "blocked"
    )

    return {
        "entries": merged,
        "agents": list(agents.values()),
        "activity_by_day": [by_day[d] for d in sorted(by_day.keys())][-7:],
        "stats": {"total": total, "completed": completed, "failed": failed},
    }


def activity_detail(profile: str, tool_call_id: str, session_id: str, message_id: str) -> dict[str, Any]:
    """Return the full tool call request + result pair for a single activity entry."""
    db = _srv()._profile_dir(profile) / "state.db"
    conn = _srv()._ro_sqlite_live(db)
    if not conn:
        return {"ok": False, "error": "state.db not found"}

    result: dict[str, Any] = {
        "ok": True,
        "profile": profile,
        "tool_call_id": tool_call_id,
        "session_id": session_id,
        "request": None,
        "response": None,
        "metadata": {},
    }

    try:
        # 1. Find the assistant message with this tool_call_id in its tool_calls JSON
        assistant_params: list[Any] = [session_id] if session_id else []
        assistant_sql = """
            SELECT m.id, m.timestamp, m.token_count, m.content, m.tool_calls, s.model
            FROM messages m
            LEFT JOIN sessions s ON s.id = m.session_id
            WHERE m.role = 'assistant'
              AND m.tool_calls IS NOT NULL
              AND m.tool_calls != '[]'
        """
        if session_id:
            assistant_sql += " AND m.session_id = ?"
        if tool_call_id:
            assistant_sql += " AND m.tool_calls LIKE ?"
            assistant_params.append(f"%{tool_call_id}%")
        assistant_sql += " ORDER BY m.timestamp DESC LIMIT 100"
        assistant_rows = conn.execute(assistant_sql, tuple(assistant_params)).fetchall()

        tool_request: dict[str, Any] | None = None
        assistant_msg_id = ""
        assistant_ts = 0.0
        model = ""

        for r in assistant_rows:
            try:
                calls = json.loads(r["tool_calls"]) if r["tool_calls"] else []
            except (json.JSONDecodeError, TypeError):
                continue
            for tc in calls:
                tc_id = tc.get("id") or tc.get("call_id") or ""
                if tc_id == tool_call_id:
                    tool_request = tc
                    assistant_msg_id = r["id"]
                    assistant_ts = r["timestamp"] or 0.0
                    model = r["model"] or ""
                    break
            if tool_request:
                break

        if not tool_request:
            return {"ok": False, "error": "tool_call_id not found in session"}

        fn = tool_request.get("function") or {}
        tool_name = fn.get("name") or "unknown"
        raw_args = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
        except (json.JSONDecodeError, TypeError):
            args = {}

        result["request"] = {
            "tool_name": tool_name,
            "arguments": args,
            "message_id": assistant_msg_id,
            "timestamp": _srv()._iso_from_unix(assistant_ts),
            "model": model,
        }

        # 2. Find the tool result message (role=tool, tool_call_id matches)
        tool_row = conn.execute(
            """
            SELECT id, timestamp, content, token_count
            FROM messages
            WHERE session_id = ?
              AND role = 'tool'
              AND tool_call_id = ?
            LIMIT 1
            """,
            (session_id, tool_call_id),
        ).fetchone()

        if tool_row:
            raw_content = tool_row["content"] or ""
            # Try to parse as JSON for structured display
            try:
                parsed_content = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
            except (json.JSONDecodeError, TypeError):
                parsed_content = None

            result["response"] = {
                "content": raw_content,
                "parsed": parsed_content,
                "message_id": tool_row["id"],
                "timestamp": _srv()._iso_from_unix(tool_row["timestamp"]),
                "token_count": tool_row["token_count"] or 0,
            }
        else:
            result["response"] = None

        # 3. Session metadata
        session_row = conn.execute(
            "SELECT title, model, message_count, started_at, ended_at, tool_call_count, input_tokens, output_tokens FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if session_row:
            result["metadata"] = {
                "session_title": session_row["title"] or "",
                "model": session_row["model"] or model,
                "message_count": session_row["message_count"] or 0,
                "started_at": _srv()._iso_from_unix(session_row["started_at"]),
                "ended_at": _srv()._iso_from_unix(session_row["ended_at"]) if session_row["ended_at"] else None,
                "tool_call_count": session_row["tool_call_count"] or 0,
                "input_tokens": session_row["input_tokens"] or 0,
                "output_tokens": session_row["output_tokens"] or 0,
            }

        # 4. Run duration (response.timestamp - request.timestamp) â€” the time the
        # tool call took. Falls back to None if either timestamp is missing.
        result["run_duration_seconds"] = None
        req_ts = result.get("request", {}).get("timestamp") if result.get("request") else None
        resp_ts = result.get("response", {}).get("timestamp") if result.get("response") else None
        if req_ts and resp_ts:
            try:
                from datetime import datetime as _dt
                req_unix = _dt.fromisoformat(req_ts).timestamp()
                resp_unix = _dt.fromisoformat(resp_ts).timestamp()
                result["run_duration_seconds"] = round(max(0.0, resp_unix - req_unix), 3)
            except (TypeError, ValueError):
                pass

        # 5. Model/provider from the profile's config.yaml. Hermes stores the
        # profile slug in sessions.model, so the BFF prefers the config value
        # when available. Falls back to sessions.model if config is missing.
        provider, config_model = _srv()._read_model_from_config(profile)
        result["model_name"] = config_model or (session_row["model"] if session_row else "") or ""
        result["provider"] = provider

    except sqlite3.Error as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()

    return result

def _message_activity_for_sessions(
    profile: str,
    crew_lookup: dict[str, Any],
    session_ids: set[str],
    limit: int = 80,
) -> list[dict[str, Any]]:
    if not session_ids:
        return []
    entries = _message_activity(profile, crew_lookup, limit * 3)
    return [entry for entry in entries if str(entry.get("session_id") or "") in session_ids][:limit]


def _room_session_activity_label(
    room_name: str,
    title: str,
    msg_count: int,
    status: str,
) -> str:
    base = str(title or room_name or "Session").strip()
    if msg_count > 0:
        return f"{base} Â· {msg_count} message{'s' if msg_count != 1 else ''}"
    if status == "active":
        return f"{base} Â· active"
    return base


def room_activity_data(
    room_id: str,
    user_id: str,
    *,
    profile_user_id: str | None = None,
) -> list[dict[str, Any]]:
    room_id = str(room_id or "").strip()
    user_id = str(user_id or "").strip()
    if not room_id or not user_id:
        return []
    conn = _srv()._workframe_db()
    try:
        room = conn.execute(
            "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
            (room_id,),
        ).fetchone()
        if not room or not _srv()._user_can_access_room(conn, room_id, user_id):
            return []
        workspace_id = str(room["workspace_id"])
        room_name = str(room["name"] or "Room")
        rows = _srv()._room_session_rows(conn, room_id)
    finally:
        conn.close()

    crew = _srv().workframe_agents().get("agents") or []
    if not isinstance(crew, list):
        crew = []
    crew_lookup = _crew_lookup(crew)
    merged: list[dict[str, Any]] = []
    session_ids_by_profile: dict[str, set[str]] = {}
    prof_uid = str(profile_user_id or user_id).strip() or user_id

    for row in rows:
        template_slug = str(row["agent_slug"] or "").strip()
        if not template_slug:
            continue
        sid = str(row["session_id"] or "").strip()
        hermes_prof = _srv()._resolve_chat_hermes_profile(template_slug, prof_uid, room_id, workspace_id)
        if not sid or not _srv()._session_exists(hermes_prof, sid):
            continue
        info = _srv()._session_info(hermes_prof, sid)
        msg_count = int(info.get("message_count") or 0)
        ended = info.get("ended_at")
        row_status = str(row["status"] or "active")
        if row_status == "active" and not ended:
            status = "active"
        elif ended:
            status = "completed"
        else:
            status = "idle"
        member = crew_lookup.get(template_slug.lower()) or crew_lookup.get(_srv()._profile_slug(template_slug).lower())
        agent = _resolve_agent(member, str(row["agent_display_name"] or _srv()._profile_display_name(template_slug)))
        title = _srv()._resolved_session_title(hermes_prof, sid, str(row["title"] or ""))
        desc = _room_session_activity_label(room_name, title, msg_count, status)
        merged.append(
            {
                "id": f"session:{hermes_prof}:{sid}",
                "kind": "session_start",
                "agent_name": agent["agent_name"],
                "profile": hermes_prof,
                "key": agent["key"],
                "task_description": desc,
                "status": status,
                "model_used": str(info.get("model") or ""),
                "created_at": _srv()._iso_from_unix(row["updated_at"] or row["created_at"]),
                "source": "session",
                "session_id": sid,
                "room_session_id": str(row["id"]),
                "message_count": msg_count,
            }
        )
        session_ids_by_profile.setdefault(hermes_prof, set()).add(sid)

    for prof, sids in session_ids_by_profile.items():
        merged.extend(_message_activity_for_sessions(prof, crew_lookup, sids, ACTIVITY_ROOM_LIMIT))

    try:
        merged.extend(run_ledger.list_run_events_for_room(room_id, limit=ACTIVITY_ROOM_LIMIT))
    except Exception:  # noqa: BLE001
        pass

    merged.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return merged[:ACTIVITY_ROOM_LIMIT]


def _room_agent_dm_owner_user_id(conn: sqlite3.Connection, room_id: str) -> str | None:
    row = conn.execute(
        """
        SELECT rm.user_id FROM room_memberships rm
        WHERE rm.room_id = ? AND rm.deleted_at IS NULL AND rm.user_id IS NOT NULL
        ORDER BY rm.joined_at ASC
        LIMIT 1
        """,
        (room_id,),
    ).fetchone()
    if not row or not row["user_id"]:
        return None
    return str(row["user_id"]).strip() or None


def workspace_activity_data(workspace_id: str, user_id: str) -> list[dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not _srv()._user_is_workspace_member(user_id, workspace_id):
        return []
    conn = _srv()._workframe_db()
    try:
        rooms = conn.execute(
            """
            SELECT id, room_type, agent_profile_id, name
            FROM rooms
            WHERE workspace_id = ? AND deleted_at IS NULL
            """,
            (workspace_id,),
        ).fetchall()
    finally:
        conn.close()
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for room in rooms:
        room_id = str(room["id"])
        profile_user_id = user_id
        if str(room["room_type"] or "") == "direct" and room["agent_profile_id"]:
            conn = _srv()._workframe_db()
            try:
                owner = _room_agent_dm_owner_user_id(conn, room_id)
            finally:
                conn.close()
            if owner:
                profile_user_id = owner
        for entry in room_activity_data(room_id, user_id, profile_user_id=profile_user_id):
            eid = str(entry.get("id") or "")
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            merged.append(entry)
    board_row = _srv()._workspace_kanban_board_row(workspace_id)
    board_slug = str(board_row["hermes_board_slug"]) if board_row else "default"
    crew = _srv().workframe_agents().get("agents") or []
    if not isinstance(crew, list):
        crew = []
    crew_lookup = _crew_lookup(crew)
    for entry in _kanban_activity(crew_lookup, 40, board_slug=board_slug):
        eid = str(entry.get("id") or "")
        if eid and eid in seen:
            continue
        if eid:
            seen.add(eid)
        merged.append(entry)
    merged.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return merged[:ACTIVITY_WORKSPACE_LIMIT]