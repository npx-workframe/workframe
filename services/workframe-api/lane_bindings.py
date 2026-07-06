"""WF-032 extract: lane_bindings."""
from __future__ import annotations

import json
import os
import queue
import re
import shlex
import shutil
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from http.server import BaseHTTPRequestHandler

import profile_config_yaml
import user_prefs


def _srv():
    import server as srv

    return srv


def _load_lane_registry() -> dict[str, Any]:
    path = _srv()._lane_registry_json()
    if not path.is_file():
        return {"profiles": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("profiles"), dict):
            return data
    except Exception:  # noqa: BLE001
        pass
    return {"profiles": {}}


def _save_lane_registry(data: dict[str, Any]) -> None:
    path = _srv()._lane_registry_json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def _binding_version(raw: Any) -> int:
    try:
        value = int(raw or 0)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0

def _binding_row_for(
    profile: str,
    source_id: str,
    client_id: str,
    binding_version: int = 0,
) -> dict[str, Any] | None:
    prof = _srv().resolve_hermes_profile(profile)
    registry = _load_lane_registry()
    bucket = _registry_profile_bucket(registry, prof)
    bindings = bucket.get("bindings") if isinstance(bucket.get("bindings"), dict) else {}
    binding_key = _source_binding_key(source_id, client_id)
    row = bindings.get(binding_key) if isinstance(bindings, dict) else None
    if not isinstance(row, dict):
        return None
    if binding_version and _binding_version(row.get("binding_version")) != binding_version:
        return None
    session_id = str(row.get("session_id") or "").strip()
    if session_id and not _srv()._session_exists(prof, session_id):
        return None
    return row

def _binding_session_for(profile: str, source_id: str, client_id: str, binding_version: int = 0) -> str:
    row = _binding_row_for(profile, source_id, client_id, binding_version)
    return str((row or {}).get("session_id") or "").strip()

def profile_chat_session(profile: str, payload: dict[str, Any], user_id: str = "") -> dict[str, Any]:
    source_id = str(payload.get("source_id") or "ui").strip() or "ui"
    client_id = str(payload.get("client_id") or "default").strip() or "default"
    binding_version = _binding_version(payload.get("binding_version"))
    force_new = bool(payload.get("new_session") or False)
    room_id = str(payload.get("room_id") or "").strip()
    user_id = str(user_id or payload.get("user_id") or "").strip()
    workspace_id = str(payload.get("workspace_id") or "").strip()
    if room_id and not workspace_id:
        try:
            conn_ws = _srv()._workframe_db()
            row = conn_ws.execute(
                "SELECT workspace_id FROM rooms WHERE id = ? AND deleted_at IS NULL",
                (room_id,),
            ).fetchone()
            conn_ws.close()
            if row:
                workspace_id = str(row["workspace_id"])
        except Exception:  # noqa: BLE001
            pass

    hermes_prof = ""
    template_prof = ""
    agent_db_id = ""
    room_conn: sqlite3.Connection | None = None

    if room_id:
        if not user_id:
            raise ValueError("room_id requires authenticated user")
        room_conn = _srv()._workframe_db()
        try:
            room = room_conn.execute(
                "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
                (room_id,),
            ).fetchone()
            if not room:
                raise ValueError("room_not_found")
            if not _srv()._user_can_access_room(room_conn, room_id, user_id):
                raise ValueError("room_access_denied")
            if not workspace_id:
                workspace_id = str(room["workspace_id"])
            if _srv()._is_space_room(str(room["room_type"]), room["agent_profile_id"]):
                raw_prof = str(profile or _srv()._primary_profile()).strip()
                if _srv()._is_runtime_profile_slug(raw_prof):
                    template_prof = _srv().resolve_validated_profile(_srv()._runtime_template_slug(raw_prof))
                    hermes_prof = raw_prof
                else:
                    template_prof = _srv().resolve_validated_profile(raw_prof)
                    hermes_prof = _srv()._resolve_chat_hermes_profile(
                        template_prof, user_id, room_id, workspace_id,
                    )
                agent_row = _srv()._lookup_agent_profile(room_conn, workspace_id, template_prof)
                if not agent_row:
                    raise ValueError("agent_profile_not_found")
                agent_db_id = str(agent_row["id"])
            else:
                _room, template_prof, hermes_prof, agent_db_id, workspace_id = _srv()._resolve_room_agent_chat(
                    room_conn, user_id, room_id,
                )
        except Exception:
            if room_conn is not None:
                room_conn.close()
            raise
    else:
        hermes_prof, template_prof = _srv()._resolve_bind_profile_arg(
            profile, user_id, "", workspace_id,
        )
    payer = user_id
    model_block = _srv()._read_model_block(hermes_prof) if hermes_prof else {}
    llm_provider = _srv()._llm_billing_provider(
        hermes_prof, user_id=payer, workspace_id=workspace_id, block=model_block,
    )
    llm_ready = _srv()._user_can_use_llm(payer, workspace_id, llm_provider) if payer else False
    # ponytail: bind = session lookup only; gateway + billing reconcile happen on send/model-save.
    api_port = _srv()._profile_api_port(hermes_prof) if hermes_prof else 0
    lifecycle = {"ok": True, "profile": hermes_prof, "api_port": api_port, "started": False}
    session_extra = {"llm_ready": llm_ready, "has_llm_provider": llm_ready}

    if room_id:
        conn = room_conn if room_conn is not None else _srv()._workframe_db()
        close_conn = room_conn is None
        try:
            existing_row = (
                None
                if force_new
                else _srv()._get_active_room_session(conn, room_id, agent_db_id)
            )
            if existing_row:
                sid = str(existing_row["session_id"]).strip()
                if not sid:
                    existing_row = None
            if existing_row:
                sid = str(existing_row["session_id"]).strip()
                gateway_sid = str(existing_row["gateway_session_id"] or f"api:{hermes_prof}:{sid}").strip()
                session_title = str(existing_row["title"] or _srv()._default_session_title(template_prof))
                if _srv()._is_blank_session_title(str(existing_row["title"] or "")):
                    _srv()._ensure_hermes_session_title(hermes_prof, sid, session_title)
                _srv()._upsert_room_session(
                    conn,
                    room_id=room_id,
                    agent_profile_id=agent_db_id,
                    session_id=sid,
                    gateway_session_id=gateway_sid,
                    created_by=user_id,
                    title=session_title,
                )
                conn.commit()
                _sync_lane_binding(
                    hermes_prof,
                    source_id,
                    client_id,
                    binding_version,
                    sid,
                    gateway_sid,
                )
                display_title = (
                    session_title
                    if not _srv()._is_blank_session_title(session_title)
                    else _srv()._resolved_session_title(hermes_prof, sid, session_title)
                )
                return {
                    "ok": True,
                    "profile": hermes_prof,
                    "template_profile": template_prof,
                    "workspace_id": workspace_id,
                    "room_id": room_id,
                    "session_id": sid,
                    "title": display_title,
                    "api_port": lifecycle["api_port"],
                    "created": False,
                    "resumed": str(existing_row["status"]) != "active",
                    **session_extra,
                }
            new_id = f"wf_room_{room_id[:8]}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            requested_title = str(payload.get("title") or "").strip() or _srv()._default_session_title(template_prof)
            status, data, session_title = _srv()._create_profile_session_via_api(hermes_prof, new_id, requested_title)
            if status >= 300:
                raise ValueError(f"create session failed: {data}")
            gateway_sid = f"api:{hermes_prof}:{new_id}"
            _srv()._upsert_room_session(
                conn,
                room_id=room_id,
                agent_profile_id=agent_db_id,
                session_id=new_id,
                gateway_session_id=gateway_sid,
                created_by=user_id,
                title=session_title or requested_title,
            )
            conn.commit()
        finally:
            if close_conn:
                conn.close()
            elif room_conn is not None:
                room_conn.close()
        _sync_lane_binding(
            hermes_prof,
            source_id,
            client_id,
            binding_version,
            new_id,
            gateway_sid,
        )
        return {
            "ok": True,
            "profile": hermes_prof,
            "template_profile": template_prof,
            "workspace_id": workspace_id,
            "room_id": room_id,
            "session_id": new_id,
            "title": session_title,
            "api_port": lifecycle["api_port"],
            "created": True,
            **session_extra,
        }

    # ponytail: legacy client_id binding when room_id omitted (tests / old clients)
    existing = "" if force_new else _binding_session_for(hermes_prof, source_id, client_id, binding_version)
    if existing and _srv()._session_exists(hermes_prof, existing):
        return {
            "ok": True,
            "profile": hermes_prof,
            "session_id": existing,
            "title": _srv()._session_info(hermes_prof, existing).get("title") or _srv()._default_session_title(template_prof),
            "api_port": lifecycle["api_port"],
            "created": False,
            **session_extra,
        }
    new_id = f"wf_{source_id}_{client_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    requested_title = str(payload.get("title") or "").strip() or _srv()._default_session_title(template_prof)
    status, data, session_title = _srv()._create_profile_session_via_api(hermes_prof, new_id, requested_title)
    if status >= 300:
        raise ValueError(f"create session failed: {data}")
    chat_dispatch(
        {
            "profile": hermes_prof,
            "session_id": new_id,
            "gateway_session_id": f"api:{hermes_prof}:{new_id}",
            "source_id": source_id,
            "client_id": client_id,
            "binding_version": binding_version,
            "text": "",
        }
    )
    return {
        "ok": True,
        "profile": hermes_prof,
        "session_id": new_id,
        "title": session_title,
        "api_port": lifecycle["api_port"],
        "created": True,
        **session_extra,
    }

def _sync_lane_binding(
    profile: str,
    source_id: str,
    client_id: str,
    binding_version: int,
    session_id: str,
    gateway_session_id: str,
    text_preview: str = "",
) -> None:
    """Keep lane-registry aligned with room_sessions for UI client/source binding."""
    # ponytail: registry bookkeeping — slug only, no Hermes disk gate
    prof = _srv().safe_profile_slug(profile)
    sid = str(session_id or "").strip()
    if not sid:
        return
    gw = str(gateway_session_id or f"api:{prof}:{sid}").strip()
    registry = _load_lane_registry()
    bucket = _registry_profile_bucket(registry, prof)
    binding_key = _source_binding_key(source_id, client_id)
    bindings = bucket.setdefault("bindings", {})
    bindings[binding_key] = {
        "session_id": sid,
        "gateway_session_id": gw,
        "binding_version": binding_version,
        "last_text_preview": str(text_preview or "")[:240],
        "source_id": source_id,
        "client_id": client_id,
        "updated_at": _srv()._utc_now(),
    }
    _save_lane_registry(registry)

def _source_binding_key(source_id: str, client_id: str) -> str:
    src = (source_id or "ui").strip().lower()
    cli = (client_id or "default").strip().lower()
    safe_src = re.sub(r"[^a-z0-9._-]+", "-", src)[:64] or "ui"
    safe_cli = re.sub(r"[^a-z0-9._-]+", "-", cli)[:96] or "default"
    return f"{safe_src}:{safe_cli}"

def _registry_profile_bucket(registry: dict[str, Any], profile: str) -> dict[str, Any]:
    profiles = registry.setdefault("profiles", {})
    bucket = profiles.setdefault(profile, {})
    bindings = bucket.setdefault("bindings", {})
    if not isinstance(bindings, dict):
        bucket["bindings"] = {}
    return bucket

def chat_resolve(payload: dict[str, Any]) -> dict[str, Any]:
    profile = _srv().resolve_hermes_profile(str(payload.get("profile") or ""))
    source_id = str(payload.get("source_id") or "ui").strip() or "ui"
    client_id = str(payload.get("client_id") or "default").strip() or "default"
    binding_version = _binding_version(payload.get("binding_version"))
    binding_key = _source_binding_key(source_id, client_id)
    row = _binding_row_for(profile, source_id, client_id, binding_version)
    session_id = str((row or {}).get("session_id") or "").strip()
    return {
        "ok": True,
        "profile": profile,
        "source_id": source_id,
        "client_id": client_id,
        "binding_key": binding_key,
        "session_id": session_id,
    }

def chat_dispatch(payload: dict[str, Any]) -> dict[str, Any]:
    profile = _srv().resolve_hermes_profile(str(payload.get("profile") or ""))
    session_id = str(payload.get("session_id") or "").strip()
    gateway_session_id = str(payload.get("gateway_session_id") or "").strip()
    source_id = str(payload.get("source_id") or "ui").strip() or "ui"
    client_id = str(payload.get("client_id") or "default").strip() or "default"
    binding_version = _binding_version(payload.get("binding_version"))
    room_id = str(payload.get("room_id") or "").strip()
    user_id = str(payload.get("user_id") or "").strip()
    text = str(payload.get("text") or "").strip()
    if not session_id:
        raise ValueError("session_id required")
    if not gateway_session_id:
        raise ValueError("gateway_session_id required")

    if room_id:
        conn = _srv()._workframe_db()
        try:
            room = conn.execute(
                "SELECT workspace_id, agent_profile_id FROM rooms WHERE id = ? AND deleted_at IS NULL",
                (room_id,),
            ).fetchone()
            agent_profile_id = ""
            if room:
                room_agent = str(room["agent_profile_id"] or "").strip()
                if room_agent:
                    agent_profile_id = room_agent
                else:
                    agent_row = _srv()._lookup_agent_profile(conn, str(room["workspace_id"]), profile)
                    agent_profile_id = str(agent_row["id"]) if agent_row else ""
            if agent_profile_id:
                _srv()._upsert_room_session(
                    conn,
                    room_id=room_id,
                    agent_profile_id=agent_profile_id,
                    session_id=session_id,
                    gateway_session_id=gateway_session_id,
                    created_by=user_id or "system",
                )
                conn.commit()
        finally:
            conn.close()
        _sync_lane_binding(
            profile,
            source_id,
            client_id,
            binding_version,
            session_id,
            gateway_session_id,
            text,
        )
        return {"ok": True, "profile": profile, "room_id": room_id, "session_id": session_id}

    registry = _load_lane_registry()
    bucket = _registry_profile_bucket(registry, profile)
    binding_key = _source_binding_key(source_id, client_id)
    bindings = bucket.setdefault("bindings", {})
    bindings[binding_key] = {
        "session_id": session_id,
        "gateway_session_id": gateway_session_id,
        "binding_version": binding_version,
        "last_text_preview": text[:240],
        "source_id": source_id,
        "client_id": client_id,
        "updated_at": _srv()._utc_now(),
    }
    _save_lane_registry(registry)
    return {"ok": True, "profile": profile, "session_id": session_id, "binding_key": binding_key}

