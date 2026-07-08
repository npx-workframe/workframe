"""WF-032 extract: chat bind and room session handlers."""
from __future__ import annotations

import re
import sqlite3
import urllib.parse
import uuid
from typing import Any

import lane_bindings


def _srv():
    import server as srv

    return srv


def room_chat_bind(room_id: str, payload: dict[str, Any], user_id: str = "") -> dict[str, Any]:
    """Room-scoped bind — identity from room.agent_profile_id, not the URL."""
    body = dict(payload or {})
    body["room_id"] = str(room_id or "").strip()
    return profile_chat_bind("", body, user_id)


def profile_chat_bind(profile: str, payload: dict[str, Any], user_id: str = "") -> dict[str, Any]:
    session = lane_bindings.profile_chat_session(profile, payload, user_id)
    sid = str(session.get("session_id") or "").strip()
    hermes_prof = str(session.get("profile") or _srv().resolve_validated_profile(profile))
    template_prof = str(session.get("template_profile") or "").strip()
    if not template_prof:
        template_prof = (
            _srv()._runtime_template_slug(hermes_prof)
            if _srv()._is_runtime_profile_slug(hermes_prof)
            else _srv().resolve_validated_profile(profile)
        )
    workspace_id = str(session.get("workspace_id") or payload.get("workspace_id") or "").strip()
    history = _srv().chat_messages(hermes_prof, sid)
    # ponytail: cohort manifest is lazy — GET /api/me/cohort; bind must stay fast
    cohort: list[dict[str, Any]] = []
    display_name = (
        _srv()._runtime_display_label(user_id, template_prof, workspace_id)
        if user_id and _srv()._is_runtime_profile_slug(hermes_prof)
        else _srv()._profile_display_name(hermes_prof, workspace_id)
    )
    return {
        "ok": True,
        "profile": session.get("profile") or profile,
        "template_profile": template_prof,
        "agent_display_name": display_name,
        "cohort": cohort,
        "session_id": sid,
        "title": session.get("title") or "",
        "created": bool(session.get("created")),
        "api_port": session.get("api_port"),
        "llm_ready": bool(session.get("llm_ready")),
        "has_llm_provider": bool(session.get("has_llm_provider")),
        "messages": history.get("messages") or [],
        "session": history.get("session") or {},
    }


def _room_session_rows(conn: sqlite3.Connection, room_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT rs.*, ap.slug AS agent_slug, ap.display_name AS agent_display_name
        FROM room_sessions rs
        LEFT JOIN agent_profiles ap ON ap.id = rs.agent_profile_id
        WHERE rs.room_id = ? AND rs.deleted_at IS NULL
        ORDER BY rs.updated_at DESC, rs.created_at DESC
        """,
        (room_id,),
    ).fetchall()


def list_room_sessions(room_id: str, user_id: str) -> dict[str, Any]:
    room_id = str(room_id or "").strip()
    user_id = str(user_id or "").strip()
    if not room_id or not user_id:
        raise ValueError("room_id and user required")
    conn = _srv()._workframe_db()
    try:
        room = conn.execute(
            "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
            (room_id,),
        ).fetchone()
        if not room:
            raise ValueError("room_not_found")
        if not _srv()._user_can_access_room(conn, room_id, user_id):
            raise ValueError("room_access_denied")
        workspace_id = str(room["workspace_id"])
        rows = _room_session_rows(conn, room_id)
    finally:
        conn.close()

    sessions: list[dict[str, Any]] = []
    for row in rows:
        template_slug = str(row["agent_slug"] or "").strip()
        agent_db_id = str(row["agent_profile_id"] or "").strip()
        if not template_slug or not agent_db_id:
            continue
        sid = str(row["session_id"] or "").strip()
        try:
            hermes_prof = _srv()._resolve_chat_hermes_profile(template_slug, user_id, room_id, workspace_id)
            if not sid or not _srv()._session_exists(hermes_prof, sid):
                continue
            info = _srv()._session_info(hermes_prof, sid)
        except ValueError:
            # ponytail: skip orphaned bindings (e.g. deleted smoke-agent profiles)
            continue
        sessions.append(
            {
                "id": str(row["id"]),
                "room_id": room_id,
                "agent_profile_id": agent_db_id,
                "agent_slug": template_slug,
                "hermes_profile": hermes_prof,
                "session_id": sid,
                "title": _srv()._resolved_session_title(hermes_prof, sid, str(row["title"] or "")),
                "status": str(row["status"] or "active"),
                "message_count": int(info.get("message_count") or 0),
                "created_at": _srv()._iso_from_unix(row["created_at"]),
                "updated_at": _srv()._iso_from_unix(row["updated_at"]),
                "active": str(row["status"] or "") == "active",
            }
        )
    return {"ok": True, "room_id": room_id, "sessions": sessions}


def profile_chat_activate_room_session(
    room_id: str,
    session_id: str,
    user_id: str,
    template_prof: str = "",
    *,
    source_id: str = "ui",
    client_id: str = "default",
    binding_version: int = 0,
) -> dict[str, Any]:
    room_id = str(room_id or "").strip()
    session_id = str(session_id or "").strip()
    user_id = str(user_id or "").strip()
    if not room_id or not session_id or not user_id:
        raise ValueError("room_id, session_id, and user required")

    conn = _srv()._workframe_db()
    try:
        room = conn.execute(
            "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
            (room_id,),
        ).fetchone()
        if not room:
            raise ValueError("room_not_found")
        if not _srv()._user_can_access_room(conn, room_id, user_id):
            raise ValueError("room_access_denied")
        workspace_id = str(room["workspace_id"])
        row = conn.execute(
            """
            SELECT rs.*, ap.slug AS agent_slug
            FROM room_sessions rs
            LEFT JOIN agent_profiles ap ON ap.id = rs.agent_profile_id
            WHERE rs.room_id = ? AND rs.session_id = ? AND rs.deleted_at IS NULL
            LIMIT 1
            """,
            (room_id, session_id),
        ).fetchone()
        if not row:
            raise ValueError("room_session_not_found")
        template_slug = str(template_prof or row["agent_slug"] or "").strip()
        if not template_slug:
            raise ValueError("agent_profile_not_found")
        agent_db_id = str(row["agent_profile_id"] or "").strip()
        hermes_prof = _srv()._resolve_chat_hermes_profile(template_slug, user_id, room_id, workspace_id)
        if not _srv()._session_exists(hermes_prof, session_id):
            raise ValueError("session_not_found")
        gateway_sid = str(row["gateway_session_id"] or f"api:{hermes_prof}:{session_id}").strip()
        title = str(_srv()._session_info(hermes_prof, session_id).get("title") or row["title"] or "")
        _srv()._upsert_room_session(
            conn,
            room_id=room_id,
            agent_profile_id=agent_db_id,
            session_id=session_id,
            gateway_session_id=gateway_sid,
            created_by=user_id,
            title=title,
        )
        conn.commit()
    finally:
        conn.close()

    lane_bindings._sync_lane_binding(
        hermes_prof,
        source_id,
        client_id,
        binding_version,
        session_id,
        gateway_sid,
    )

    if user_id:
        _srv()._reconcile_profile_llm_for_user(hermes_prof, user_id, workspace_id)
    llm_provider = _srv()._llm_billing_provider(hermes_prof, user_id=user_id, workspace_id=workspace_id)
    llm_ready = _srv()._overlay_chat_llm_env(hermes_prof, user_id, workspace_id, llm_provider)

    history = _srv().chat_messages(hermes_prof, session_id)
    cohort = _srv().ensure_user_agent_cohort(user_id, workspace_id)
    return {
        "ok": True,
        "profile": hermes_prof,
        "template_profile": template_slug,
        "agent_display_name": _srv()._runtime_display_label(user_id, template_slug, workspace_id),
        "cohort": cohort,
        "room_id": room_id,
        "session_id": session_id,
        "title": title,
        "created": False,
        "resumed": True,
        "llm_ready": llm_ready,
        "has_llm_provider": llm_ready,
        "messages": history.get("messages") or [],
        "session": history.get("session") or {},
    }


def profile_chat_message(profile: str, payload: dict[str, Any]) -> dict[str, Any]:
    source_id = str(payload.get("source_id") or "ui").strip() or "ui"
    client_id = str(payload.get("client_id") or "default").strip() or "default"
    session_id = str(payload.get("session_id") or "").strip()
    text = str(payload.get("text") or "").strip()
    if not session_id:
        raise ValueError("session_id required")
    if not text:
        raise ValueError("text required")
    payer = str(payload.get("user_id") or "").strip()
    workspace_id = str(payload.get("workspace_id") or "").strip()
    room_id = str(payload.get("room_id") or "").strip()
    hermes_prof, _template_prof = _srv()._resolve_bind_profile_arg(
        profile, payer, room_id, workspace_id,
    )
    if payer:
        _srv()._reconcile_profile_llm_for_user(hermes_prof, payer, workspace_id)
    llm_provider = _srv()._llm_billing_provider(hermes_prof, user_id=payer, workspace_id=workspace_id)
    lifecycle = _srv().ensure_profile_api(
        hermes_prof,
        payer,
        workspace_id,
    )
    turn_run_id = str(uuid.uuid4())
    try:
        if payer:
            _srv()._overlay_turn_provider_env(
                hermes_prof, payer, workspace_id, llm_provider, turn_run_id,
            )
            _srv()._overlay_turn_user_env(hermes_prof, payer, workspace_id, turn_run_id)
        turn_body = _srv()._profile_turn_payload(hermes_prof, text, room_id)
        if payer and workspace_id:
            _srv()._inject_turn_credentials(turn_body, payer, workspace_id, llm_provider)
        status, data = _srv()._profile_api_request(
            hermes_prof,
            "POST",
            f"/api/sessions/{urllib.parse.quote(session_id, safe='')}/chat",
            turn_body,
        )
        if status >= 300:
            raise ValueError(f"session chat failed: {data}")
        assistant = ""
        if isinstance(data, dict):
            msg = data.get("message")
            if isinstance(msg, dict):
                assistant = str(msg.get("content") or "")
        lane_bindings.chat_dispatch(
            {
                "profile": hermes_prof,
                "session_id": session_id,
                "gateway_session_id": f"api:{hermes_prof}:{session_id}",
                "source_id": source_id,
                "client_id": client_id,
                "room_id": room_id,
                "user_id": payer,
                "text": text,
            }
        )
        return {
            "ok": True,
            "profile": hermes_prof,
            "session_id": session_id,
            "api_port": lifecycle["api_port"],
            "assistant": assistant,
        }
    finally:
        if payer:
            _srv()._revoke_turn_credential_lease(turn_run_id, hermes_prof)


def _enrich_room_chat_payload(payload: dict[str, Any], user_id: str) -> dict[str, Any]:
    body = dict(payload) if isinstance(payload, dict) else {}
    body["user_id"] = user_id
    room_id = str(body.get("room_id") or "").strip()
    if room_id and not str(body.get("workspace_id") or "").strip():
        try:
            conn = _srv()._workframe_db()
            row = conn.execute(
                "SELECT workspace_id FROM rooms WHERE id = ? AND deleted_at IS NULL",
                (room_id,),
            ).fetchone()
            conn.close()
            if row:
                body["workspace_id"] = str(row["workspace_id"])
        except Exception:  # noqa: BLE001
            pass
    return body


def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+)$", line.strip())
        if m:
            return m.group(1).strip()
    return fallback
