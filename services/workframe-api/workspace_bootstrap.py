"""WF-032 extract: workspace bootstrap and onboarding helpers."""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from typing import Any


def _srv():
    import server as srv

    return srv


def _provision_invited_member_agent_runtimes(workspace_id: str, user_id: str) -> bool:
    """Provision u-* runtimes for workspace agents when a member joins."""
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not workspace_id or not user_id:
        return False
    try:
        conn = _srv()._workframe_db()
        rows = conn.execute(
            """
            SELECT id FROM agent_profiles
            WHERE workspace_id = ? AND deleted_at IS NULL AND status = 'available'
            """,
            (workspace_id,),
        ).fetchall()
        conn.close()
    except Exception:  # noqa: BLE001
        return False
    ok = True
    for row in rows:
        if not _provision_agent_dm_runtimes(workspace_id, str(row["id"]), [user_id]):
            ok = False
    return ok


def _provision_agent_dm_runtimes(
    workspace_id: str,
    agent_profile_id: str,
    user_ids: list[str],
) -> bool:
    """Create u-* runtime profiles when an agent DM room is created — install/onboarding only, not bind."""
    workspace_id = str(workspace_id or "").strip()
    agent_profile_id = str(agent_profile_id or "").strip()
    if not workspace_id or not agent_profile_id:
        return False
    try:
        conn = _srv()._workframe_db()
        agent_row = _srv()._lookup_agent_profile(conn, workspace_id, agent_profile_id)
        conn.close()
    except Exception:  # noqa: BLE001
        return False
    if not agent_row:
        return False
    template = str(agent_row["slug"] or "").strip()
    if not template:
        return False
    try:
        template = _srv().resolve_validated_profile(template)
    except ValueError as exc:
        print(
            f"[provision_agent_dm_runtimes] skip {agent_profile_id}: invalid template {template!r}: {exc}",
            flush=True,
        )
        return False
    ok = True
    for uid in user_ids:
        user = str(uid or "").strip()
        if not user:
            continue
        runtime = _srv()._runtime_profile_slug(user, template)
        if _srv()._runtime_profile_on_disk(runtime):
            continue
        try:
            _srv().ensure_runtime_profile(runtime, template, user, workspace_id)
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(
                f"[provision_agent_dm_runtimes] failed {runtime} for {user}: {exc}",
                flush=True,
            )
    return ok


def bootstrap_agent_dm_lane(
    user_id: str,
    workspace_id: str,
    template_slug: str,
    *,
    model: str = "",
    soul: str = "",
    bind_session: bool = True,
    room_name: str = "",
    role: str = "",
    tagline: str = "",
    created_by: str = "",
) -> dict[str, Any]:
    """Provision u-* runtime, model/proxy, DM room, and optional session bind — install/create-agent parity."""
    user_id = str(user_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if not _srv()._native_profile_present():
        _srv()._ensure_native_hermes_profile()
    template = _srv().resolve_validated_profile(str(template_slug or "").strip())
    if not user_id or not workspace_id:
        return {"ok": False, "error": "user_id and workspace_id required"}
    runtime = _srv()._runtime_profile_slug(user_id, template)
    steps: list[dict[str, Any]] = []
    try:
        _srv().ensure_runtime_profile(runtime, template, user_id, workspace_id)
        steps.append({"step": "runtime_profile", "ok": True, "runtime": runtime})
    except Exception as exc:
        steps.append({"step": "runtime_profile", "ok": False, "error": str(exc)})
        return {"ok": False, "template": template, "runtime": runtime, "steps": steps, "error": str(exc)}

    model_id = str(model or "").strip()
    if model_id:
        try:
            applied = _srv().hermes_model_set(runtime, model_id, user_id, workspace_id)
            steps.append(
                {
                    "step": "set_runtime_model",
                    "ok": bool(applied.get("ok")),
                    "model": model_id,
                    **({"error": applied.get("error")} if not applied.get("ok") else {}),
                },
            )
            if not applied.get("ok"):
                return {
                    "ok": False,
                    "template": template,
                    "runtime": runtime,
                    "steps": steps,
                    "error": str(applied.get("error") or "set_runtime_model_failed"),
                }
        except Exception as exc:
            steps.append({"step": "set_runtime_model", "ok": False, "error": str(exc)})
            return {
                "ok": False,
                "template": template,
                "runtime": runtime,
                "steps": steps,
                "error": str(exc),
            }
    else:
        try:
            _srv()._bootstrap_profile_providers(runtime, user_id, workspace_id)
            steps.append({"step": "bootstrap_providers", "ok": True})
            user_primary, user_chain = _srv()._read_user_llm_prefs(user_id)
            if user_primary:
                applied = _srv().hermes_model_set(runtime, user_primary, user_id, workspace_id)
                steps.append(
                    {
                        "step": "user_default_model",
                        "ok": bool(applied.get("ok")),
                        "model": user_primary,
                    },
                )
            if user_chain:
                chained = _srv().hermes_fallback_chain_set(runtime, user_chain, user_id=user_id)
                steps.append(
                    {
                        "step": "user_default_fallbacks",
                        "ok": bool(chained.get("ok")),
                        "count": len(user_chain),
                    },
                )
        except Exception as exc:
            steps.append({"step": "bootstrap_providers", "ok": False, "error": str(exc)})

    soul_text = str(soul or "").strip()
    identity_role = str(role or "").strip()
    identity_tagline = str(tagline or "").strip()
    identity_name = room_name.strip()
    if soul_text or identity_name or identity_role or identity_tagline:
        _srv()._seed_native_user_overlay(
            runtime,
            template,
            display_name=identity_name,
            role=identity_role,
            tagline=identity_tagline,
            user_soul=soul_text,
        )

    gateway_started = False
    last_gw_exc: Exception | None = None
    for attempt in range(3):
        try:
            _srv().ensure_profile_api(runtime, user_id, workspace_id, bootstrap_providers=False)
            step_row: dict[str, Any] = {"step": "start_gateway", "ok": True, "runtime": runtime}
            if attempt:
                step_row["retried"] = True
            steps.append(step_row)
            gateway_started = True
            break
        except Exception as exc:
            last_gw_exc = exc
            if attempt < 2:
                time.sleep(1.5)
    if not gateway_started:
        steps.append({"step": "start_gateway", "ok": False, "error": str(last_gw_exc)})
        return {
            "ok": False,
            "template": template,
            "runtime": runtime,
            "steps": steps,
            "error": str(last_gw_exc),
        }

    display = _srv()._runtime_display_label(user_id, template, workspace_id)
    _srv()._ensure_workspace_agent_profile_row(
        template,
        workspace_id=workspace_id,
        display_name=room_name.strip() or display,
        role=identity_role,
        tagline=identity_tagline,
        is_native=_srv()._is_native_profile(template),
    )
    status, room_payload = _srv()._create_room(
        workspace_id,
        {
            "name": room_name.strip() or display,
            "room_type": "direct",
            "agent_profile_id": template,
            "member_user_ids": [user_id],
        },
        created_by or user_id,
    )
    room = room_payload.get("room") if isinstance(room_payload.get("room"), dict) else {}
    room_id = str(room.get("id") or "").strip()
    dm_error = ""
    if not room_id:
        dm_error = str(
            room_payload.get("error")
            or room_payload.get("detail")
            or ("dm_room_failed" if status not in (200, 201) else "dm_room_missing_id"),
        ).strip()
    steps.append(
        {
            "step": "dm_room",
            "ok": status in (200, 201) and bool(room_id),
            "room_id": room_id,
            "status": status,
            **({"error": dm_error} if dm_error else {}),
        },
    )
    if not room_id:
        return {
            "ok": False,
            "template": template,
            "runtime": runtime,
            "steps": steps,
            "error": dm_error or "dm_room_failed",
            "room_error": room_payload,
        }

    session_id = ""
    if bind_session:
        bind_payload: dict[str, Any] = {
            "workspace_id": workspace_id,
            "source_id": "ui",
            "client_id": "default",
            "new_session": False,
        }
        if template == _srv()._primary_profile():
            bind_payload["binding_version"] = 2
        try:
            bound = _srv().room_chat_bind(room_id, bind_payload, user_id)
            session_id = str(bound.get("session_id") or "").strip()
            steps.append({"step": "room_chat_bind", "ok": bool(session_id), "session_id": session_id})
        except Exception as exc:
            steps.append({"step": "room_chat_bind", "ok": False, "error": str(exc)})

    bind_ok = not bind_session or bool(session_id)
    steps_ok = all(s.get("ok") is not False for s in steps)
    return {
        "ok": bind_ok and steps_ok,
        "template": template,
        "runtime": runtime,
        "room_id": room_id,
        "room": room,
        "session_id": session_id,
        "steps": steps,
        **({"error": "room_chat_bind_failed"} if bind_session and not session_id else {}),
    }


def _onboard_workspace_member_rooms(
    conn: sqlite3.Connection,
    workspace_id: str,
    user_id: str,
    *,
    inviter_user_id: str | None = None,
) -> dict[str, Any]:
    room_join = _join_workspace_default_room(
        conn,
        workspace_id,
        user_id,
        inviter_user_id=inviter_user_id,
    )
    spaces_joined = _srv()._add_workspace_member_to_space_rooms(conn, workspace_id, user_id)
    return {**room_join, "spaces_joined": spaces_joined}


def _join_workspace_default_room(
    conn: sqlite3.Connection,
    workspace_id: str,
    user_id: str,
    *,
    inviter_user_id: str | None = None,
) -> dict[str, Any]:
    room = _srv()._default_workspace_room(conn, workspace_id)
    if not room:
        return {"room_id": None, "joined": False}
    room_id = str(room["id"])
    joined = _srv()._ensure_user_in_room(conn, room_id, user_id)
    inviter_joined = False
    if inviter_user_id and inviter_user_id != user_id:
        inviter_joined = _srv()._ensure_user_in_room(conn, room_id, inviter_user_id)
    return {
        "room_id": room_id,
        "room_slug": str(room["slug"]),
        "joined": joined,
        "inviter_joined": inviter_joined,
    }


def _ensure_user_dm_room(
    conn: sqlite3.Connection,
    workspace_id: str,
    user_a: str,
    user_b: str,
) -> dict[str, Any]:
    """Idempotent DM between two workspace users (no agent)."""
    left_id, right_id = sorted([str(user_a).strip(), str(user_b).strip()])
    if not left_id or not right_id or left_id == right_id:
        return {"room_id": None, "created": False}
    existing = conn.execute(
        """
        SELECT id FROM rooms
        WHERE workspace_id = ?
          AND room_type = 'direct'
          AND deleted_at IS NULL
          AND agent_profile_id IS NULL
          AND EXISTS (
              SELECT 1 FROM room_memberships rm
              WHERE rm.room_id = rooms.id AND rm.deleted_at IS NULL AND rm.user_id = ?
          )
          AND EXISTS (
              SELECT 1 FROM room_memberships rm
              WHERE rm.room_id = rooms.id AND rm.deleted_at IS NULL AND rm.user_id = ?
          )
          AND NOT EXISTS (
              SELECT 1 FROM room_memberships rm
              WHERE rm.room_id = rooms.id AND rm.deleted_at IS NULL AND rm.user_id NOT IN (?, ?)
          )
        LIMIT 1
        """,
        (workspace_id, left_id, right_id, left_id, right_id),
    ).fetchone()
    if existing:
        return {"room_id": str(existing["id"]), "created": False}
    now = str(int(time.time()))
    room_id = str(uuid.uuid4())
    slug = _srv()._normalize_room_slug(f"dm-{left_id}-{right_id}", "dm")
    conn.execute(
        """
        INSERT INTO rooms
            (id, workspace_id, agent_profile_id, name, slug, topic, room_type, status, created_by, created_at, updated_at)
        VALUES (?, ?, NULL, ?, ?, '', 'direct', 'active', ?, ?, ?)
        """,
        (room_id, workspace_id, "DM", slug, left_id, now, now),
    )
    for uid in (left_id, right_id):
        _srv()._ensure_user_in_room(conn, room_id, uid)
    return {"room_id": room_id, "created": True}


def _promote_workspace_owner_if_unclaimed(conn: sqlite3.Connection, workspace_id: str, user_id: str) -> bool:
    if not _srv()._install_window_open():
        return False
    row = conn.execute(
        "SELECT owner_id FROM workspaces WHERE id = ? AND deleted_at IS NULL",
        (workspace_id,),
    ).fetchone()
    if not row:
        return False
    if str(row["owner_id"] or "").strip():
        return False
    now = str(int(time.time()))
    conn.execute(
        "UPDATE workspaces SET owner_id = ?, updated_at = ? WHERE id = ?",
        (user_id, now, workspace_id),
    )
    mem = conn.execute(
        "SELECT id FROM workspace_memberships WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL",
        (workspace_id, user_id),
    ).fetchone()
    if mem:
        conn.execute(
            "UPDATE workspace_memberships SET role = ?, updated_at = ? WHERE id = ?",
            ("owner", now, mem["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO workspace_memberships
            (id, workspace_id, user_id, role, status, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (str(uuid.uuid4()), workspace_id, user_id, "owner", "active", now, now),
        )
    return True


def _sync_workspace_home_room(conn: sqlite3.Connection, workspace_id: str) -> None:
    """Keep slug=general space aligned with workspace display_name, tagline, avatar."""
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return
    ws_row = conn.execute(
        "SELECT display_name, avatar_url, settings_json FROM workspaces WHERE id = ? AND deleted_at IS NULL",
        (workspace_id,),
    ).fetchone()
    if not ws_row:
        return
    settings = _srv()._parse_workspace_settings(ws_row)
    name = str(ws_row["display_name"] or "").strip() or "Workspace"
    tagline = str(settings.get("tagline") or "").strip()
    avatar = str(ws_row["avatar_url"] or "").strip() or None
    now = str(int(time.time()))
    room = conn.execute(
        """
        SELECT id FROM rooms
        WHERE workspace_id = ? AND slug = 'general' AND deleted_at IS NULL
        """,
        (workspace_id,),
    ).fetchone()
    if room:
        conn.execute(
            """
            UPDATE rooms
            SET name = ?, topic = ?, avatar_url = COALESCE(?, avatar_url), updated_at = ?
            WHERE id = ?
            """,
            (name, tagline, avatar, now, str(room["id"])),
        )


def _ensure_default_workspace() -> bool:
    """Idempotent first-run DB seed: Workframe workspace + native agent + General room."""
    project_name = str(os.environ.get("WORKFRAME_PROJECT", "Workframe") or "Workframe").strip() or "Workframe"
    native_slug = str(_srv().NATIVE_PROFILE or "workframe-agent").strip() or "workframe-agent"
    native_display = f"{project_name} Agent"
    conn = _srv()._workframe_db()
    try:
        ws = conn.execute(
            "SELECT id FROM workspaces WHERE slug = 'default' AND deleted_at IS NULL",
        ).fetchone()
        now = str(int(time.time()))
        if not ws:
            ws_id = str(uuid.uuid4())
            settings = json.dumps({
                "credential_mode": "byok",
                "admin_onboarding_done": False,
                "admin_integrations_done": False,
            })
            ws_logo = _srv()._pick_logo_url() or None
            conn.execute(
                """
                INSERT INTO workspaces (
                    id, slug, display_name, description, owner_id, status,
                    settings_json, avatar_url, created_at, updated_at
                ) VALUES (?, 'default', ?, '', '', 'active', ?, ?, ?, ?)
                """,
                (ws_id, project_name, settings, ws_logo, now, now),
            )
        else:
            ws_id = str(ws["id"])
        ws_row = conn.execute(
            "SELECT display_name, avatar_url, settings_json FROM workspaces WHERE id = ?",
            (ws_id,),
        ).fetchone()
        settings = _srv()._parse_workspace_settings(ws_row) if ws_row else {}
        home_name = str(ws_row["display_name"] or "").strip() if ws_row else project_name
        home_name = home_name or project_name
        home_tagline = str(settings.get("tagline") or "").strip()
        home_avatar = str(ws_row["avatar_url"] or "").strip() if ws_row else ""
        if not home_avatar:
            home_avatar = _srv()._pick_logo_url() or ""
        room = conn.execute(
            """
            SELECT id FROM rooms
            WHERE workspace_id = ? AND slug = 'general' AND deleted_at IS NULL
            """,
            (ws_id,),
        ).fetchone()
        if not room:
            conn.execute(
                """
                INSERT INTO rooms (
                    id, workspace_id, name, slug, topic, avatar_url, room_type, status, created_at, updated_at
                ) VALUES (?, ?, ?, 'general', ?, ?, 'channel', 'active', ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    ws_id,
                    home_name,
                    home_tagline,
                    home_avatar or None,
                    now,
                    now,
                ),
            )
        _sync_workspace_home_room(conn, ws_id)
        conn.commit()
    finally:
        conn.close()
    _srv()._ensure_workspace_agent_profile_row(
        native_slug,
        display_name=native_display,
        role="native",
        is_native=True,
    )
    return True


def _bootstrap_after_setup(agent_personality: str = "") -> dict[str, Any]:
    """ponytail: verify native gateway after setup; optional SOUL overlay from onboarding text."""
    profile = _srv()._primary_profile()
    result: dict[str, Any] = {"profile": profile}
    personality = str(agent_personality or "").strip()
    if personality:
        _srv()._seed_native_user_overlay(profile, profile, user_soul=personality)
        result["soul_seeded"] = True
    return result
