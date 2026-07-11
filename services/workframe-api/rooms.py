"""WF-032 extract: rooms."""
from __future__ import annotations

import json
import os
import queue
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from http.server import BaseHTTPRequestHandler

import user_prefs
import zk_auth as _zk
from auth_gate import OWNER_ADMIN_ROLES, SECURE_MODE, role_allows as _role_allows

_room_live_lock = threading.Lock()
_room_live_queues: dict[str, list[queue.SimpleQueue[str]]] = {}
_room_live_turns: dict[str, dict[str, Any]] = {}


def _srv():
    import server as srv

    return srv


def _room_live_subscribe(room_id: str) -> queue.SimpleQueue[str]:
    q: queue.SimpleQueue[str] = queue.SimpleQueue()
    with _room_live_lock:
        _room_live_queues.setdefault(room_id, []).append(q)
    return q


def _room_live_unsubscribe(room_id: str, q: queue.SimpleQueue[str]) -> None:
    with _room_live_lock:
        subs = _room_live_queues.get(room_id, [])
        if q in subs:
            subs.remove(q)
        if not subs:
            _room_live_queues.pop(room_id, None)


def _room_live_publish(room_id: str, event: dict[str, Any]) -> None:
    line = json.dumps(event)
    with _room_live_lock:
        subs = list(_room_live_queues.get(room_id, []))
    for sub in subs:
        try:
            sub.put(line)
        except Exception:  # noqa: BLE001
            pass


def _room_live_set_turn(turn: dict[str, Any]) -> None:
    with _room_live_lock:
        _room_live_turns[str(turn["turn_id"])] = turn


def _room_live_clear_turn(turn_id: str) -> None:
    with _room_live_lock:
        _room_live_turns.pop(str(turn_id), None)


def _room_live_active_for_room(room_id: str) -> list[dict[str, Any]]:
    with _room_live_lock:
        return [dict(turn) for turn in _room_live_turns.values() if str(turn.get("room_id") or "") == room_id]




def _room_payload(row: sqlite3.Row) -> dict[str, Any]:
    """Return the API-safe payload for a room row."""
    platform_ids_raw = row["platform_ids"] or "{}"
    try:
        platform_ids = json.loads(platform_ids_raw) if isinstance(platform_ids_raw, str) else platform_ids_raw
    except (TypeError, json.JSONDecodeError):
        platform_ids = {}
    if not isinstance(platform_ids, dict):
        platform_ids = {}
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "agent_profile_id": row["agent_profile_id"],
        "name": row["name"],
        "slug": row["slug"],
        "topic": row["topic"] or "",
        "avatar_url": row["avatar_url"] if "avatar_url" in row.keys() else None,
        "room_type": row["room_type"],
        "platform_ids": platform_ids,
        "status": row["status"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _sanitize_space_room_agent_fields(room: dict[str, Any]) -> None:
    """Spaces never bind a single agent on the room row — agents live in memberships."""
    if str(room.get("room_type") or "") in {"channel", "group"}:
        room["agent_profile_id"] = None
        room["hermes_profile"] = None


def _workspace_payload(row: sqlite3.Row, *, viewer_role: str = "") -> dict[str, Any]:
    keys = row.keys()
    settings = _srv()._parse_workspace_settings(row)
    payload: dict[str, Any] = {
        "id": row["id"],
        "slug": row["slug"],
        "display_name": row["display_name"] or "",
        "description": row["description"] if "description" in keys else "",
        "avatar_url": row["avatar_url"] if "avatar_url" in keys else None,
        "status": row["status"],
        "owner_id": row["owner_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    gh = settings.get("github_oauth") if isinstance(settings.get("github_oauth"), dict) else {}
    stack_gh = _srv()._github_oauth_app_config("")
    integrations: dict[str, Any] = {
        "github_oauth_configured": _srv()._github_oauth_configured(str(row["id"]))
        or bool(stack_gh.get("client_id") and stack_gh.get("client_secret")),
    }
    if viewer_role in OWNER_ADMIN_ROLES:
        integrations["github_oauth_client_id"] = str(gh.get("client_id") or stack_gh.get("client_id") or "")
        integrations["github_oauth_has_secret"] = bool(
            str(gh.get("client_secret") or "").strip()
            or (not gh and stack_gh.get("client_secret"))
        )
        integrations["messaging"] = _srv()._workspace_messaging_integrations_payload(str(row["id"]), settings)
    payload["integrations"] = integrations
    payload["credential_mode"] = str(settings.get("credential_mode") or "byok").strip() or "byok"
    payload["tagline"] = str(settings.get("tagline") or "")
    if viewer_role in OWNER_ADMIN_ROLES:
        payload["admin_onboarding_done"] = bool(settings.get("admin_onboarding_done"))
    return payload


def _normalize_room_slug(value: str, fallback: str = "") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower())
    slug = slug.strip("-")
    if not slug:
        slug = f"room-{fallback[:8]}" if fallback else "room"
    if len(slug) > 64:
        slug = slug[:64].rstrip("-") or "room"
    return slug


def _parse_room_platform_ids(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("platform_ids must be a JSON object") from exc
        if not isinstance(parsed, dict):
            raise ValueError("platform_ids must be a JSON object")
        return parsed
    raise ValueError("platform_ids must be an object")


def _resolve_wid(workspace_id_or_slug: str) -> str | None:
    """Resolve a workspace identifier (UUID or slug) to its UUID.
    
    Returns the UUID string if found, or None if the workspace doesn't exist.
    Opens and closes its own DB connection — use once per request, or pass
    the resolved UUID downstream.
    """
    val = str(workspace_id_or_slug or "").strip()
    if not val:
        return None
    try:
        conn = _srv()._workframe_db()
        row = conn.execute(
            "SELECT id FROM workspaces WHERE (id = ? OR slug = ?) AND deleted_at IS NULL",
            (val, val),
        ).fetchone()
        conn.close()
        return str(row["id"]) if row else None
    except Exception:
        return None


def _workspace_exists(conn: sqlite3.Connection, workspace_id: str) -> bool:
    row = conn.execute(
        "SELECT id FROM workspaces WHERE id = ? AND deleted_at IS NULL",
        (workspace_id,),
    ).fetchone()
    return row is not None


def _workspace_member_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "membership_id": row["membership_id"],
        "workspace_id": row["workspace_id"],
        "user_id": row["user_id"],
        "email": row["email"],
        "display_name": row["display_name"] or "",
        "avatar_url": row["avatar_url"],
        "role": row["role"],
        "status": row["status"],
        "invited_by": row["invited_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _workspace_member_lookup_sql() -> str:
    return """
        SELECT
            wm.membership_id,
            wm.workspace_id,
            wm.user_id,
            wm.role,
            wm.status,
            wm.invited_by,
            wm.created_at,
            wm.updated_at,
            wm.email,
            wm.display_name,
            wm.avatar_url
        FROM (
            SELECT
                wm.id AS membership_id,
                wm.workspace_id,
                wm.user_id,
                wm.role,
                wm.status,
                wm.invited_by,
                wm.created_at,
                wm.updated_at,
                u.email,
                u.display_name,
                u.avatar_url,
                ROW_NUMBER() OVER (
                    PARTITION BY wm.workspace_id, wm.user_id
                    ORDER BY wm.created_at ASC, wm.id ASC
                ) AS membership_rank
            FROM workspace_memberships wm
            LEFT JOIN users u ON u.id = wm.user_id
            WHERE wm.workspace_id = ?
              AND wm.deleted_at IS NULL
        ) wm
        WHERE wm.membership_rank = 1
    """


def _workspace_member_role(
    conn: sqlite3.Connection,
    workspace_id: str,
    user_id: str,
) -> str | None:
    row = conn.execute(
        """
        SELECT wm.role
        FROM workspace_memberships wm
        JOIN workspaces w ON w.id = wm.workspace_id
        WHERE wm.workspace_id = ?
          AND wm.user_id = ?
          AND wm.deleted_at IS NULL
          AND wm.status = 'active'
          AND w.deleted_at IS NULL
          AND w.status = 'active'
        """,
        (workspace_id, user_id),
    ).fetchone()
    return str(row["role"]) if row else None


_ONBOARDING_PROGRESS_KEYS = frozenset({
    "admin_integrations_done",
    "admin_onboarding_done",
    "credential_mode",
})


def _resolve_workspace_integrations_role(
    conn: sqlite3.Connection,
    workspace_id: str,
    user_id: str,
    body: dict[str, Any],
) -> str | None:
    """Owner/admin for integrations; repair stale membership during install onboarding."""
    role = _srv()._workspace_member_role(conn, workspace_id, user_id)
    row = conn.execute(
        "SELECT owner_id FROM workspaces WHERE id = ? AND deleted_at IS NULL",
        (workspace_id,),
    ).fetchone()
    owner_id = str(row["owner_id"] or "").strip() if row else ""
    now = str(int(time.time()))

    if owner_id and owner_id == user_id and role not in OWNER_ADMIN_ROLES:
        mem = conn.execute(
            "SELECT id FROM workspace_memberships WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL",
            (workspace_id, user_id),
        ).fetchone()
        if mem:
            conn.execute(
                "UPDATE workspace_memberships SET role = 'owner', updated_at = ? WHERE id = ?",
                (now, mem["id"]),
            )
        role = "owner"
    elif not owner_id and _srv()._install_window_open():
        if _srv()._promote_workspace_owner_if_unclaimed(conn, workspace_id, user_id):
            role = _srv()._workspace_member_role(conn, workspace_id, user_id)

    if role in OWNER_ADMIN_ROLES:
        return role
    if (
        role
        and _srv()._install_window_open()
        and set(body.keys()) <= _ONBOARDING_PROGRESS_KEYS
    ):
        return role
    return role


def _can_read_workspace_members(
    handler: BaseHTTPRequestHandler,
    conn: sqlite3.Connection,
    workspace_id: str,
) -> bool:
    if not SECURE_MODE:
        return True
    if _role_allows(handler, OWNER_ADMIN_ROLES):
        return True
    user_id = str(getattr(handler, "auth_user", "") or "")
    return _srv()._workspace_member_role(conn, workspace_id, user_id) is not None


def _can_manage_workspace_members(
    handler: BaseHTTPRequestHandler,
    conn: sqlite3.Connection,
    workspace_id: str,
) -> bool:
    if not SECURE_MODE:
        return True
    if _role_allows(handler, OWNER_ADMIN_ROLES):
        return True
    user_id = str(getattr(handler, "auth_user", "") or "")
    return _srv()._workspace_member_role(conn, workspace_id, user_id) in OWNER_ADMIN_ROLES


def _list_workspace_members(
    workspace_id: str,
    handler: BaseHTTPRequestHandler | None = None,
) -> tuple[int, dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return 400, {"ok": False, "error": "workspace_id required"}
    try:
        conn = _srv()._workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        if not _workspace_exists(conn, workspace_id):
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        if handler is not None and not _can_read_workspace_members(handler, conn, workspace_id):
            return 403, {"ok": False, "error": "forbidden", "required_role": "workspace_member_or_owner_or_admin"}
        rows = conn.execute(
            f"{_workspace_member_lookup_sql()} ORDER BY COALESCE(wm.display_name, wm.email, wm.user_id) ASC, wm.created_at ASC",
            (workspace_id,),
        ).fetchall()
        members: list[dict[str, Any]] = []
        for row in rows:
            payload = _workspace_member_payload(row)
            prof = _zk.get_profile(str(row["user_id"]))
            if isinstance(prof, dict):
                if prof.get("tagline"):
                    payload["tagline"] = str(prof["tagline"])
                zk_avatar = str(prof.get("avatar_url") or "").strip()
                if zk_avatar:
                    payload["avatar_url"] = _srv()._normalize_user_avatar_url(zk_avatar)
            members.append(payload)
        return 200, {
            "ok": True,
            "workspace_id": workspace_id,
            "members": members,
        }
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workspace_member_list_failed: {exc}"}
    finally:
        conn.close()


def _active_owner_count(conn: sqlite3.Connection, workspace_id: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM workspace_memberships
        WHERE workspace_id = ?
          AND deleted_at IS NULL
          AND status = 'active'
          AND role = 'owner'
        """,
        (workspace_id,),
    ).fetchone()
    return int(row["c"] if row else 0)


def _workspace_membership_update_payload(
    conn: sqlite3.Connection,
    workspace_id: str,
    user_id: str,
    updates: dict[str, Any],
    actor_user_id: str,
) -> tuple[int, dict[str, Any]]:
    membership_id = str(updates.get("membership_id", "") or "").strip()
    if membership_id:
        row = conn.execute(
            f"{_workspace_member_lookup_sql()} AND wm.membership_id = ?",
            (workspace_id, membership_id),
        ).fetchone()
    else:
        row = conn.execute(
            f"{_workspace_member_lookup_sql()} AND wm.user_id = ?",
            (workspace_id, user_id),
        ).fetchone()
    if not row:
        return 404, {"ok": False, "error": "member_not_found", "workspace_id": workspace_id, "user_id": user_id}

    role = str(row["role"])
    status = str(row["status"])
    if "role" in updates:
        role = str(updates.get("role", "") or "").strip()
        if role not in WORKSPACE_MEMBER_ROLES:
            return 400, {"ok": False, "error": "invalid_role", "allowed": sorted(WORKSPACE_MEMBER_ROLES)}
    if "status" in updates:
        status = str(updates.get("status", "") or "").strip()
        if status not in WORKSPACE_MEMBER_STATUSES:
            return 400, {"ok": False, "error": "invalid_status", "allowed": sorted(WORKSPACE_MEMBER_STATUSES)}
    if bool(updates.get("remove", False)) or bool(updates.get("delete", False)):
        status = "removed"

    if role == "owner" and status == "active":
        owners = _active_owner_count(conn, workspace_id)
        existing_role = str(row["role"])
        existing_status = str(row["status"])
        if existing_role != "owner" or existing_status != "active":
            owners += 1
    else:
        owners = _active_owner_count(conn, workspace_id)
        existing_role = str(row["role"])
        existing_status = str(row["status"])
        if existing_role == "owner" and existing_status == "active":
            owners -= 1
    if owners < 1:
        return 409, {"ok": False, "error": "cannot_remove_last_owner", "workspace_id": workspace_id}

    now_ts = str(int(time.time()))
    deleted_at = now_ts if status == "removed" else None
    try:
        conn.execute(
            """
            UPDATE workspace_memberships
            SET role = ?, status = ?, deleted_at = ?, invited_by = COALESCE(invited_by, ?), updated_at = ?
            WHERE id = ?
            """,
            (role, status, deleted_at, actor_user_id or None, now_ts, row["membership_id"]),
        )
    except sqlite3.IntegrityError as exc:
        return 409, {"ok": False, "error": "workspace_membership_update_conflict", "detail": str(exc)}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workspace_membership_update_failed: {exc}"}

    updated = conn.execute(
        """
        SELECT
            wm.id AS membership_id,
            wm.workspace_id,
            wm.user_id,
            wm.role,
            wm.status,
            wm.invited_by,
            wm.created_at,
            wm.updated_at,
            u.email,
            u.display_name,
            u.avatar_url
        FROM workspace_memberships wm
        LEFT JOIN users u ON u.id = wm.user_id
        WHERE wm.workspace_id = ? AND wm.id = ?
        """,
        (workspace_id, row["membership_id"]),
    ).fetchone()
    if not updated:
        return 404, {"ok": False, "error": "member_not_found", "workspace_id": workspace_id, "user_id": user_id}
    return 200, {"ok": True, "membership": _workspace_member_payload(updated)}


def _patch_workspace_members(
    workspace_id: str,
    body: dict[str, Any],
    handler: BaseHTTPRequestHandler,
) -> tuple[int, dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return 400, {"ok": False, "error": "workspace_id required"}
    if not isinstance(body, dict):
        body = {}

    bulk = body.get("memberships")
    if bulk is None:
        bulk = body.get("members")
    if bulk is not None and not isinstance(bulk, list):
        return 400, {"ok": False, "error": "memberships must be a list"}

    try:
        conn = _srv()._workframe_db()
        actor_user_id = getattr(handler, "auth_user", "")
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        if not _workspace_exists(conn, workspace_id):
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        if not _can_manage_workspace_members(handler, conn, workspace_id):
            return 403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"}

        if isinstance(bulk, list):
            if not bulk:
                return 400, {"ok": False, "error": "memberships list cannot be empty"}
            results = []
            for item in bulk:
                if not isinstance(item, dict):
                    return 400, {"ok": False, "error": "each membership update must be an object"}
                user_id = str(item.get("user_id", "") or "").strip()
                if not user_id and not str(item.get("membership_id", "") or "").strip():
                    return 400, {"ok": False, "error": "user_id or membership_id required"}
                status, payload = _workspace_membership_update_payload(conn, workspace_id, user_id, item, actor_user_id)
                if status != 200:
                    return status, payload
                results.append(payload["membership"])
            conn.commit()
            return 200, {"ok": True, "workspace_id": workspace_id, "memberships": results}

        user_id = str(body.get("user_id", "") or "").strip()
        membership_id = str(body.get("membership_id", "") or "").strip()
        if not user_id and not membership_id:
            return 400, {"ok": False, "error": "user_id or membership_id required"}
        update_body = dict(body)
        if membership_id:
            update_body["membership_id"] = membership_id
        status, payload = _workspace_membership_update_payload(conn, workspace_id, user_id, update_body, actor_user_id)
        if status == 200:
            conn.commit()
        return status, payload
    except sqlite3.Error as exc:
        conn.rollback()
        return 500, {"ok": False, "error": f"workspace_member_patch_failed: {exc}"}
    finally:
        conn.close()


_AGENT_PROFILE_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _lookup_agent_profile(
    conn: sqlite3.Connection,
    workspace_id: str,
    ref: str,
) -> sqlite3.Row | None:
    """Resolve workspace agent_profiles row by canonical id or Hermes slug."""
    ref = str(ref or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if not ref or not workspace_id:
        return None
    if _AGENT_PROFILE_UUID_RE.match(ref):
        return conn.execute(
            """
            SELECT id, workspace_id, slug, display_name, role, tagline, is_native, status
            FROM agent_profiles
            WHERE id = ? AND workspace_id = ? AND deleted_at IS NULL
            """,
            (ref, workspace_id),
        ).fetchone()
    return conn.execute(
        """
        SELECT id, workspace_id, slug, display_name, role, tagline, is_native, status
        FROM agent_profiles
        WHERE slug = ? AND workspace_id = ? AND deleted_at IS NULL
        """,
        (ref, workspace_id),
    ).fetchone()


def _hermes_slug_from_agent_ref(ref: str) -> str:
    """Map workspace agent_profiles.id to Hermes profile slug."""
    ref = str(ref or "").strip()
    if not ref or not _AGENT_PROFILE_UUID_RE.match(ref):
        return ref
    try:
        conn = _srv()._workframe_db()
        row = conn.execute(
            "SELECT slug FROM agent_profiles WHERE id = ? AND deleted_at IS NULL LIMIT 1",
            (ref,),
        ).fetchone()
        conn.close()
        return str(row["slug"]) if row else ""
    except Exception:
        return ""


def _enrich_rooms_hermes_profile(conn: sqlite3.Connection, rooms: list[dict[str, Any]]) -> None:
    ids = {
        str(room["agent_profile_id"])
        for room in rooms
        if room.get("agent_profile_id") and str(room.get("room_type") or "") == "direct"
    }
    by_id: dict[str, str] = {}
    if ids:
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"""
            SELECT id, slug FROM agent_profiles
            WHERE id IN ({placeholders}) AND deleted_at IS NULL
            """,
            tuple(ids),
        ).fetchall()
        by_id = {str(row["id"]): str(row["slug"]) for row in rows}
    for room in rooms:
        ref = str(room.get("agent_profile_id") or "")
        if not ref:
            room["hermes_profile"] = None
        elif ref in by_id:
            room["hermes_profile"] = by_id[ref]
        elif not _AGENT_PROFILE_UUID_RE.match(ref):
            room["hermes_profile"] = ref
        else:
            room["hermes_profile"] = None
    for room in rooms:
        _sanitize_space_room_agent_fields(room)


def _ensure_workspace_agent_profile_row(
    slug: str,
    *,
    workspace_id: str = "",
    display_name: str = "",
    role: str = "",
    tagline: str = "",
    is_native: bool = False,
) -> str | None:
    """Ensure agent_profiles row exists for a workspace (default workspace when id omitted)."""
    slug = str(slug or "").strip()
    if not slug:
        return None
    conn: sqlite3.Connection | None = None
    try:
        conn = _srv()._workframe_db()
        ws_id = str(workspace_id or "").strip()
        if ws_id:
            ws = conn.execute(
                "SELECT id FROM workspaces WHERE id = ? AND deleted_at IS NULL",
                (ws_id,),
            ).fetchone()
        else:
            ws = conn.execute(
                """
                SELECT id FROM workspaces
                WHERE deleted_at IS NULL
                ORDER BY CASE WHEN slug = 'default' THEN 0 ELSE 1 END, created_at ASC
                LIMIT 1
                """,
            ).fetchone()
        if not ws:
            return None
        ws_id = str(ws["id"])
        existing = conn.execute(
            """
            SELECT id FROM agent_profiles
            WHERE workspace_id = ? AND slug = ? AND deleted_at IS NULL
            """,
            (ws_id, slug),
        ).fetchone()
        if existing:
            agent_id = str(existing["id"])
            patches: dict[str, Any] = {}
            if display_name.strip():
                patches["display_name"] = display_name.strip()
            if tagline.strip():
                patches["tagline"] = tagline.strip()
            if role.strip():
                patches["role"] = role.strip()
            if patches:
                sets = [f"{col} = ?" for col in patches]
                vals = list(patches.values()) + [str(int(time.time())), ws_id, slug]
                conn.execute(
                    f"UPDATE agent_profiles SET {', '.join(sets)}, updated_at = ? WHERE workspace_id = ? AND slug = ? AND deleted_at IS NULL",
                    vals,
                )
            _srv()._add_workspace_agents_to_space_rooms(conn, ws_id, agent_id)
            conn.commit()
            return agent_id
        agent_id = str(uuid.uuid4())
        now = str(int(time.time()))
        reg = _srv()._agent_registry_row(slug)
        avatar_url = str(reg.get("avatar_url") or "").strip() or None
        if not avatar_url and not reg.get("avatar_id"):
            try:
                picked = _srv()._assign_agent_avatar(slug)
                avatar_url = picked.get("avatar_url")
            except Exception:
                avatar_url = None
        conn.execute(
            """
            INSERT INTO agent_profiles (
                id, workspace_id, slug, display_name, tagline, role, avatar_url,
                is_native, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'available', ?, ?)
            """,
            (
                agent_id,
                ws_id,
                slug,
                display_name.strip() or slug,
                tagline.strip(),
                role.strip(),
                avatar_url,
                1 if is_native else 0,
                now,
                now,
            ),
        )
        conn.commit()
        _srv()._add_workspace_agents_to_space_rooms(conn, ws_id, agent_id)
        return agent_id
    except Exception:
        return None
    finally:
        if conn is not None:
            conn.close()


def _room_api_payload(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    room = _room_payload(row)
    _enrich_rooms_hermes_profile(conn, [room])
    return room


def _agent_profile_belongs(conn: sqlite3.Connection, agent_profile_id: str, workspace_id: str) -> bool:
    return _srv()._lookup_agent_profile(conn, workspace_id, agent_profile_id) is not None


def _room_slug_available(conn: sqlite3.Connection, workspace_id: str, slug: str, room_id: str = "") -> bool:
    row = conn.execute(
        """
        SELECT id FROM rooms
        WHERE workspace_id = ? AND slug = ? AND deleted_at IS NULL
        """,
        (workspace_id, slug),
    ).fetchone()
    return row is None or (room_id and row["id"] == room_id)


def _list_rooms(workspace_id: str, *, include_members: bool = False) -> tuple[int, dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return 400, {"ok": False, "error": "workspace_id required"}
    try:
        conn = _srv()._workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        if not _workspace_exists(conn, workspace_id):
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        rows = conn.execute(
            """
            SELECT id, workspace_id, agent_profile_id, name, slug, topic, avatar_url, room_type,
                   platform_ids, status, created_by, created_at, updated_at
            FROM rooms
            WHERE workspace_id = ? AND deleted_at IS NULL
            ORDER BY created_at ASC, name ASC
            """,
            (workspace_id,),
        ).fetchall()
        rooms = [_room_payload(row) for row in rows]
        _enrich_rooms_hermes_profile(conn, rooms)
        if include_members and rooms:
            room_ids = [str(room["id"]) for room in rooms]
            placeholders = ",".join("?" * len(room_ids))
            member_rows = conn.execute(
                f"""
                SELECT room_id, user_id
                FROM room_memberships
                WHERE deleted_at IS NULL AND room_id IN ({placeholders})
                """,
                room_ids,
            ).fetchall()
            members_by_room: dict[str, list[str]] = {}
            for member_row in member_rows:
                members_by_room.setdefault(str(member_row["room_id"]), []).append(str(member_row["user_id"]))
            for room in rooms:
                room["member_user_ids"] = members_by_room.get(str(room["id"]), [])
        return 200, {"ok": True, "workspace_id": workspace_id, "rooms": rooms}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"room_list_failed: {exc}"}
    finally:
        conn.close()


def _patch_room(room_id: str, body: dict[str, Any], user_id: str) -> tuple[int, dict[str, Any]]:
    room_id = str(room_id or "").strip()
    user_id = str(user_id or "").strip()
    if not room_id:
        return 400, {"ok": False, "error": "room_id required"}
    if not user_id:
        return 401, {"ok": False, "error": "no_session"}
    allowed = {"name", "topic", "avatar_url"}
    updates = {key: str(body[key]).strip() for key in allowed if key in body}
    if not updates:
        return 400, {"ok": False, "error": "no_allowed_fields", "allowed": list(allowed)}
    if "avatar_url" in updates:
        _srv()._validate_me_profile_updates({"avatar_url": updates["avatar_url"]})
        updates["avatar_url"] = _srv()._normalize_logo_url(updates["avatar_url"])
    if "name" in updates and not updates["name"]:
        return 400, {"ok": False, "error": "name required"}
    try:
        conn = _srv()._workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        row = conn.execute(
            "SELECT id, workspace_id FROM rooms WHERE id = ? AND deleted_at IS NULL",
            (room_id,),
        ).fetchone()
        if not row:
            return 404, {"ok": False, "error": "room_not_found", "room_id": room_id}
        if not _user_can_access_room(conn, room_id, user_id):
            return 403, {"ok": False, "error": "forbidden"}
        workspace_id = str(row["workspace_id"])
        member = conn.execute(
            """
            SELECT role FROM workspace_memberships
            WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL AND status = 'active'
            """,
            (workspace_id, user_id),
        ).fetchone()
        if not member or str(member["role"]) not in {"owner", "admin"}:
            return 403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"}
        sets = [f"{key} = ?" for key in updates]
        vals = list(updates.values())
        now_ts = str(int(time.time()))
        sets.extend(["updated_at = ?"])
        vals.extend([now_ts, room_id])
        conn.execute(f"UPDATE rooms SET {', '.join(sets)} WHERE id = ?", vals)
        conn.commit()
        updated = conn.execute(
            """
            SELECT id, workspace_id, agent_profile_id, name, slug, topic, avatar_url, room_type,
                   platform_ids, status, created_by, created_at, updated_at
            FROM rooms WHERE id = ?
            """,
            (room_id,),
        ).fetchone()
        if not updated:
            return 500, {"ok": False, "error": "room_lookup_failed"}
        return 200, {"ok": True, "room": _room_api_payload(conn, updated)}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"room_update_failed: {exc}"}
    finally:
        conn.close()


def _get_workspace(workspace_id: str, user_id: str) -> tuple[int, dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not workspace_id:
        return 400, {"ok": False, "error": "workspace_id required"}
    if not user_id:
        return 401, {"ok": False, "error": "no_session"}
    try:
        conn = _srv()._workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        if not _workspace_exists(conn, workspace_id):
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        if _srv()._workspace_member_role(conn, workspace_id, user_id) is None:
            return 403, {"ok": False, "error": "forbidden"}
        role = _srv()._workspace_member_role(conn, workspace_id, user_id) or ""
        row = conn.execute(
            "SELECT * FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        if not row:
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        return 200, {"ok": True, "workspace": _workspace_payload(row, viewer_role=role)}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workspace_lookup_failed: {exc}"}
    finally:
        conn.close()


def _patch_workspace(workspace_id: str, body: dict[str, Any], user_id: str) -> tuple[int, dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not workspace_id:
        return 400, {"ok": False, "error": "workspace_id required"}
    if not user_id:
        return 401, {"ok": False, "error": "no_session"}
    allowed = {"display_name", "description", "avatar_url", "tagline"}
    updates = {key: str(body[key]).strip() for key in ("display_name", "description", "avatar_url") if key in body}
    tagline = str(body.get("tagline") or "").strip() if "tagline" in body else None
    if not updates and tagline is None:
        return 400, {"ok": False, "error": "no_allowed_fields", "allowed": list(allowed)}
    if "avatar_url" in updates:
        _srv()._validate_me_profile_updates({"avatar_url": updates["avatar_url"]})
        updates["avatar_url"] = _srv()._normalize_logo_url(updates["avatar_url"])
    if "display_name" in updates and not updates["display_name"]:
        return 400, {"ok": False, "error": "display_name required"}
    try:
        conn = _srv()._workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        if not _workspace_exists(conn, workspace_id):
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        role = _resolve_workspace_integrations_role(conn, workspace_id, user_id, {})
        if not role or (
            role not in OWNER_ADMIN_ROLES and not _srv()._install_window_open()
        ):
            return 403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"}
        member_role = str(role)
        row = conn.execute(
            "SELECT * FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        if not row:
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        sets = [f"{key} = ?" for key in updates]
        vals = list(updates.values())
        now_ts = str(int(time.time()))
        if tagline is not None:
            settings = _srv()._parse_workspace_settings(row)
            settings["tagline"] = tagline
            sets.append("settings_json = ?")
            vals.append(json.dumps(settings, sort_keys=True))
        sets.append("updated_at = ?")
        vals.extend([now_ts, workspace_id])
        conn.execute(f"UPDATE workspaces SET {', '.join(sets)} WHERE id = ?", vals)
        _srv()._sync_workspace_home_room(conn, workspace_id)
        conn.commit()
        row = conn.execute(
            "SELECT * FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        if not row:
            return 500, {"ok": False, "error": "workspace_lookup_failed"}
        return 200, {"ok": True, "workspace": _workspace_payload(row, viewer_role=member_role)}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workspace_update_failed: {exc}"}
    finally:
        conn.close()


def _patch_workspace_integrations(
    workspace_id: str,
    body: dict[str, Any],
    user_id: str,
) -> tuple[int, dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not workspace_id or not user_id:
        return 401, {"ok": False, "error": "no_session"}
    try:
        conn = _srv()._workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        if not _workspace_exists(conn, workspace_id):
            return 404, {"ok": False, "error": "workspace_not_found"}
        role = _resolve_workspace_integrations_role(conn, workspace_id, user_id, body)
        if role not in OWNER_ADMIN_ROLES and not (
            role and _srv()._install_window_open() and set(body.keys()) <= _ONBOARDING_PROGRESS_KEYS
        ):
            return 403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"}
        row = conn.execute(
            "SELECT * FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        if not row:
            return 404, {"ok": False, "error": "workspace_not_found"}
        settings = _srv()._parse_workspace_settings(row)
        gh = settings.get("github_oauth") if isinstance(settings.get("github_oauth"), dict) else {}
        if "github_oauth_client_id" in body:
            gh["client_id"] = str(body.get("github_oauth_client_id") or "").strip()
        if "github_oauth_client_secret" in body:
            secret = str(body.get("github_oauth_client_secret") or "").strip()
            if secret:
                gh["client_secret"] = secret
        if gh:
            settings["github_oauth"] = gh
        if "credential_mode" in body:
            mode = str(body.get("credential_mode") or "byok").strip().lower()
            if mode not in {"byok", "workspace"}:
                return 400, {"ok": False, "error": "invalid_credential_mode"}
            settings["credential_mode"] = mode
        if body.get("admin_onboarding_done") is True:
            settings["admin_onboarding_done"] = True
        if body.get("admin_integrations_done") is True:
            settings["admin_integrations_done"] = True
        settings = _srv()._parse_messaging_settings_patch(body, settings)
        now_ts = str(int(time.time()))
        conn.execute(
            "UPDATE workspaces SET settings_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(settings, sort_keys=True), now_ts, workspace_id),
        )
        conn.commit()
        if "messaging" in body:
            sync_result = _srv()._sync_workspace_messaging_gateway(workspace_id)
            if not sync_result.get("ok"):
                return 500, {"ok": False, "error": sync_result.get("error") or "messaging_sync_failed"}
        updated = conn.execute(
            "SELECT * FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        if not updated:
            return 500, {"ok": False, "error": "workspace_lookup_failed"}
        return 200, {"ok": True, "workspace": _workspace_payload(updated, viewer_role=role or "")}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workspace_integrations_update_failed: {exc}"}
    finally:
        conn.close()


def _get_room(room_id: str) -> tuple[int, dict[str, Any]]:
    room_id = str(room_id or "").strip()
    if not room_id:
        return 400, {"ok": False, "error": "room_id required"}
    try:
        conn = _srv()._workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        row = conn.execute(
            """
            SELECT id, workspace_id, agent_profile_id, name, slug, topic, avatar_url, room_type,
                   platform_ids, status, created_by, created_at, updated_at
            FROM rooms
            WHERE id = ? AND deleted_at IS NULL
            """,
            (room_id,),
        ).fetchone()
        if not row:
            return 404, {"ok": False, "error": "room_not_found", "room_id": room_id}
        return 200, {"ok": True, "room": _room_api_payload(conn, row)}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"room_lookup_failed: {exc}"}
    finally:
        conn.close()


def _create_room(workspace_id: str, body: dict[str, Any], created_by: str) -> tuple[int, dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return 400, {"ok": False, "error": "workspace_id required"}
    name = str(body.get("name", "") or "").strip()
    if not name:
        return 400, {"ok": False, "error": "name required"}

    room_type = str(body.get("room_type", "channel") or "channel").strip() or "channel"
    if room_type not in {"lane", "group", "direct", "channel"}:
        return 400, {"ok": False, "error": "invalid_room_type", "allowed": ["lane", "group", "direct", "channel"]}

    topic = str(body.get("topic", "") or "").strip()
    agent_profile_id = str(body.get("agent_profile_id", "") or "").strip() or None
    status = str(body.get("status", "active") or "active").strip() or "active"
    if status not in {"active", "archived", "locked"}:
        return 400, {"ok": False, "error": "invalid_room_status", "allowed": ["active", "archived", "locked"]}

    member_user_ids = body.get("member_user_ids", [])
    if member_user_ids in (None, ""):
        member_user_ids = []
    if not isinstance(member_user_ids, list):
        return 400, {"ok": False, "error": "member_user_ids must be a list"}
    member_user_ids = [str(user_id).strip() for user_id in member_user_ids if str(user_id).strip()]

    try:
        platform_ids = _parse_room_platform_ids(body.get("platform_ids", {}))
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}

    base_slug = _normalize_room_slug(str(body.get("slug", "") or ""), name)
    rid = str(uuid.uuid4())
    now_ts = str(int(time.time()))
    try:
        conn = _srv()._workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        if not _workspace_exists(conn, workspace_id):
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        if agent_profile_id and not _agent_profile_belongs(conn, agent_profile_id, workspace_id):
            return 400, {"ok": False, "error": "agent_profile_not_found", "agent_profile_id": agent_profile_id}
        agent_row = (
            _srv()._lookup_agent_profile(conn, workspace_id, agent_profile_id) if agent_profile_id else None
        )
        agent_profile_id = str(agent_row["id"]) if agent_row else agent_profile_id

        direct_member_ids = sorted({user_id for user_id in member_user_ids if user_id})
        if room_type == 'direct':
            existing_row = None
            if agent_profile_id and direct_member_ids:
                existing_row = conn.execute(
                    """
                    SELECT id, workspace_id, agent_profile_id, name, slug, topic, avatar_url, room_type,
                           platform_ids, status, created_by, created_at, updated_at
                    FROM rooms
                    WHERE workspace_id = ?
                      AND room_type = 'direct'
                      AND deleted_at IS NULL
                      AND agent_profile_id = ?
                      AND EXISTS (
                          SELECT 1 FROM room_memberships rm
                          WHERE rm.room_id = rooms.id
                            AND rm.deleted_at IS NULL
                            AND rm.user_id = ?
                      )
                    LIMIT 1
                    """,
                    (workspace_id, agent_profile_id, direct_member_ids[0]),
                ).fetchone()
            elif len(direct_member_ids) == 2:
                left_id, right_id = direct_member_ids
                existing_row = conn.execute(
                    """
                    SELECT id, workspace_id, agent_profile_id, name, slug, topic, avatar_url, room_type,
                           platform_ids, status, created_by, created_at, updated_at
                    FROM rooms
                    WHERE workspace_id = ?
                      AND room_type = 'direct'
                      AND deleted_at IS NULL
                      AND agent_profile_id IS NULL
                      AND EXISTS (
                          SELECT 1 FROM room_memberships rm
                          WHERE rm.room_id = rooms.id
                            AND rm.deleted_at IS NULL
                            AND rm.user_id = ?
                      )
                      AND EXISTS (
                          SELECT 1 FROM room_memberships rm
                          WHERE rm.room_id = rooms.id
                            AND rm.deleted_at IS NULL
                            AND rm.user_id = ?
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM room_memberships rm
                          WHERE rm.room_id = rooms.id
                            AND rm.deleted_at IS NULL
                            AND rm.user_id NOT IN (?, ?)
                      )
                    LIMIT 1
                    """,
                    (workspace_id, left_id, right_id, left_id, right_id),
                ).fetchone()
            if existing_row:
                return 200, {"ok": True, "room": _room_api_payload(conn, existing_row)}

        slug = base_slug
        if room_type == 'direct' and direct_member_ids:
            if agent_profile_id and len(direct_member_ids) == 1:
                slug = _normalize_room_slug(f"dm-{direct_member_ids[0]}-{agent_profile_id}", name)
            elif len(direct_member_ids) == 2:
                slug = _normalize_room_slug(f"dm-{direct_member_ids[0]}-{direct_member_ids[1]}", name)
        for attempt in range(1, 26):
            if _room_slug_available(conn, workspace_id, slug):
                break
            slug = f"{base_slug}-{attempt}"
        else:
            return 409, {"ok": False, "error": "room_slug_conflict", "slug": base_slug}

        platform_json = json.dumps(platform_ids, sort_keys=True)
        explicit_avatar = str(body.get("avatar_url", "") or "").strip()
        if explicit_avatar:
            explicit_avatar = _srv()._normalize_logo_url(explicit_avatar)
        room_avatar_url = explicit_avatar or (
            _srv()._pick_logo_url() if _srv()._is_space_room(room_type, agent_profile_id) else ""
        )
        conn.execute(
            """
            INSERT INTO rooms (
                id, workspace_id, agent_profile_id, name, slug, topic, avatar_url, room_type,
                platform_ids, status, created_by, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rid,
                workspace_id,
                agent_profile_id,
                name,
                slug,
                topic,
                room_avatar_url or None,
                room_type,
                platform_json,
                status,
                created_by or None,
                now_ts,
                now_ts,
            ),
        )
        if created_by:
            _ensure_user_in_room(conn, rid, created_by)
        if member_user_ids:
            seen: set[str] = set()
            for user_id in member_user_ids:
                if user_id in seen:
                    continue
                seen.add(user_id)
                membership_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO room_memberships (id, room_id, user_id, role, status, joined_at, updated_at)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (membership_id, rid, user_id, "member", "active", now_ts, now_ts),
                )
        if _srv()._is_space_room(room_type, agent_profile_id):
            agents = conn.execute(
                "SELECT id FROM agent_profiles WHERE workspace_id = ? AND deleted_at IS NULL",
                (workspace_id,),
            ).fetchall()
            for agent in agents:
                _srv()._ensure_agent_in_space_room(conn, rid, str(agent["id"]))
            _srv()._add_workspace_members_to_space_room(conn, workspace_id, rid)
        elif room_type == "direct" and agent_profile_id and direct_member_ids:
            _srv()._provision_agent_dm_runtimes(workspace_id, agent_profile_id, direct_member_ids)
        conn.commit()
        row = conn.execute(
            """
            SELECT id, workspace_id, agent_profile_id, name, slug, topic, avatar_url, room_type,
                   platform_ids, status, created_by, created_at, updated_at
            FROM rooms
            WHERE id = ?
            """,
            (rid,),
        ).fetchone()
        if not row:
            return 500, {"ok": False, "error": "room_create_failed"}
        return 201, {"ok": True, "room": _room_api_payload(conn, row)}
    except sqlite3.IntegrityError as exc:
        return 409, {"ok": False, "error": "room_already_exists", "detail": str(exc)}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"room_create_failed: {exc}"}
    finally:
        conn.close()


def _default_workspace_room(conn: sqlite3.Connection, workspace_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, slug, name
        FROM rooms
        WHERE workspace_id = ? AND deleted_at IS NULL
        ORDER BY CASE slug WHEN 'general' THEN 0 ELSE 1 END, created_at ASC
        LIMIT 1
        """,
        (workspace_id,),
    ).fetchone()


def _ensure_user_in_room(conn: sqlite3.Connection, room_id: str, user_id: str, role: str = "member") -> bool:
    existing = conn.execute(
        "SELECT id FROM room_memberships WHERE room_id = ? AND user_id = ? AND deleted_at IS NULL",
        (room_id, user_id),
    ).fetchone()
    if existing:
        return False
    now = str(int(time.time()))
    conn.execute(
        """
        INSERT INTO room_memberships (id, room_id, user_id, role, status, joined_at, updated_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        (str(uuid.uuid4()), room_id, user_id, role, "active", now, now),
    )
    return True


def _workspace_credential_mode(conn: sqlite3.Connection | None, workspace_id: str) -> str:
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return "byok"
    own_conn = False
    if conn is None:
        conn = _srv()._workframe_db()
        own_conn = True
    try:
        row = conn.execute(
            "SELECT settings_json FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        settings = _srv()._parse_workspace_settings(row) if row else {}
        mode = str(settings.get("credential_mode") or "byok").strip().lower()
        return mode if mode in ("byok", "workspace") else "byok"
    except sqlite3.Error:
        # Before bootstrap creates the workspace schema, BYOK is the safe default.
        return "byok"
    finally:
        if own_conn:
            conn.close()


def _user_can_access_room(conn: sqlite3.Connection, room_id: str, user_id: str) -> bool:
    user_id = str(user_id or "").strip()
    if not user_id:
        return False
    row = conn.execute(
        """
        SELECT 1 FROM room_memberships
        WHERE room_id = ? AND user_id = ? AND deleted_at IS NULL AND status = 'active'
        LIMIT 1
        """,
        (room_id, user_id),
    ).fetchone()
    if row is not None:
        return True
    # ponytail: repair pre-fix rooms that never added creator membership
    creator = conn.execute(
        "SELECT created_by FROM rooms WHERE id = ? AND deleted_at IS NULL",
        (room_id,),
    ).fetchone()
    if creator and str(creator["created_by"] or "") == user_id:
        _ensure_user_in_room(conn, room_id, user_id)
        conn.commit()
        return True
    return False


def _user_can_manage_room_members(conn: sqlite3.Connection, room_id: str, user_id: str) -> bool:
    user_id = str(user_id or "").strip()
    if not user_id or not _user_can_access_room(conn, room_id, user_id):
        return False
    row = conn.execute(
        """
        SELECT role FROM room_memberships
        WHERE room_id = ? AND user_id = ? AND deleted_at IS NULL AND status = 'active'
        LIMIT 1
        """,
        (room_id, user_id),
    ).fetchone()
    if row and str(row["role"] or "").strip().lower() in {"admin", "owner"}:
        return True
    room = conn.execute(
        "SELECT workspace_id FROM rooms WHERE id = ? AND deleted_at IS NULL",
        (room_id,),
    ).fetchone()
    if room:
        ws_id = str(room["workspace_id"] or "").strip()
        if ws_id and _srv()._workspace_member_role(conn, ws_id, user_id) in OWNER_ADMIN_ROLES:
            return True
    return False


def _get_active_room_session(
    conn: sqlite3.Connection,
    room_id: str,
    agent_profile_id: str = "",
) -> sqlite3.Row | None:
    room_id = str(room_id or "").strip()
    agent_profile_id = str(agent_profile_id or "").strip()
    if not room_id:
        return None
    if agent_profile_id:
        return conn.execute(
            """
            SELECT * FROM room_sessions
            WHERE room_id = ? AND agent_profile_id = ? AND deleted_at IS NULL AND status = 'active'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (room_id, agent_profile_id),
        ).fetchone()
    return conn.execute(
        """
        SELECT * FROM room_sessions
        WHERE room_id = ? AND deleted_at IS NULL AND status = 'active'
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (room_id,),
    ).fetchone()


def _list_room_sessions(
    conn: sqlite3.Connection,
    room_id: str,
    agent_profile_id: str,
) -> list[sqlite3.Row]:
    room_id = str(room_id or "").strip()
    agent_profile_id = str(agent_profile_id or "").strip()
    if not room_id or not agent_profile_id:
        return []
    return conn.execute(
        """
        SELECT * FROM room_sessions
        WHERE room_id = ? AND agent_profile_id = ? AND deleted_at IS NULL
        ORDER BY updated_at DESC, created_at DESC
        """,
        (room_id, agent_profile_id),
    ).fetchall()


def _resolve_latest_room_session(
    conn: sqlite3.Connection,
    profile: str,
    room_id: str,
    agent_profile_id: str,
) -> sqlite3.Row | None:
    """Active room_sessions row for this room+agent whose Hermes session still exists."""
    for row in _list_room_sessions(conn, room_id, agent_profile_id):
        if str(row["status"] or "").strip() != "active":
            continue
        sid = str(row["session_id"] or "").strip()
        if sid and _session_exists(profile, sid):
            return row
    return None


def _archive_room_sessions(
    conn: sqlite3.Connection,
    room_id: str,
    agent_profile_id: str = "",
) -> None:
    now = str(int(time.time()))
    room_id = str(room_id or "").strip()
    agent_profile_id = str(agent_profile_id or "").strip()
    if agent_profile_id:
        conn.execute(
            """
            UPDATE room_sessions
            SET status = 'archived', updated_at = ?
            WHERE room_id = ? AND agent_profile_id = ? AND deleted_at IS NULL AND status = 'active'
            """,
            (now, room_id, agent_profile_id),
        )
        return
    conn.execute(
        """
        UPDATE room_sessions
        SET status = 'archived', updated_at = ?
        WHERE room_id = ? AND deleted_at IS NULL AND status = 'active'
        """,
        (now, room_id),
    )


def _upsert_room_session(
    conn: sqlite3.Connection,
    *,
    room_id: str,
    agent_profile_id: str,
    session_id: str,
    gateway_session_id: str,
    created_by: str,
    title: str = "",
) -> None:
    now = str(int(time.time()))
    room_id = str(room_id or "").strip()
    agent_profile_id = str(agent_profile_id or "").strip()
    session_id = str(session_id or "").strip()
    prior = conn.execute(
        """
        SELECT id, session_id, status FROM room_sessions
        WHERE room_id = ? AND agent_profile_id = ? AND session_id = ? AND deleted_at IS NULL
        LIMIT 1
        """,
        (room_id, agent_profile_id, session_id),
    ).fetchone()
    if prior:
        _archive_room_sessions(conn, room_id, agent_profile_id)
        conn.execute(
            """
            UPDATE room_sessions
            SET status = 'active', gateway_session_id = ?, updated_at = ?,
                title = COALESCE(NULLIF(?, ''), title), created_by = COALESCE(?, created_by)
            WHERE id = ?
            """,
            (gateway_session_id, now, title, created_by or None, prior["id"]),
        )
        return
    _archive_room_sessions(conn, room_id, agent_profile_id)
    conn.execute(
        """
        INSERT INTO room_sessions (
            id, room_id, agent_profile_id, session_id, gateway_session_id,
            title, status, created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            room_id,
            agent_profile_id,
            session_id,
            gateway_session_id,
            title,
            created_by,
            now,
            now,
        ),
    )


def _room_session_context(
    conn: sqlite3.Connection,
    user_id: str,
    room_id: str,
    hermes_slug: str,
) -> tuple[sqlite3.Row, str, str]:
    """Validate access and resolve (room, hermes slug, agent_profiles.id) for session bind."""
    room_id = str(room_id or "").strip()
    user_id = str(user_id or "").strip()
    hermes_slug = str(hermes_slug or "").strip()
    if not room_id:
        raise ValueError("room_id required")
    if not user_id:
        raise ValueError("authenticated user required")
    if not hermes_slug:
        raise ValueError("profile required")
    if not _user_can_access_room(conn, room_id, user_id):
        raise ValueError("room_access_denied")
    room = conn.execute(
        "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
        (room_id,),
    ).fetchone()
    if not room:
        raise ValueError("room_not_found")
    if _srv()._is_space_room(str(room["room_type"]), None):
        raise ValueError("room_not_agent_chat")
    workspace_id = str(room["workspace_id"])
    agent_row = _srv()._lookup_agent_profile(conn, workspace_id, hermes_slug)
    if not agent_row:
        raise ValueError("agent_profile_not_found")
    agent_db_id = str(agent_row["id"])
    room_agent_ref = str(room["agent_profile_id"] or "").strip()
    if room_agent_ref:
        room_agent = _srv()._lookup_agent_profile(conn, workspace_id, room_agent_ref)
        if not room_agent or str(room_agent["id"]) != agent_db_id:
            raise ValueError("profile does not match room agent")
    elif not _srv()._is_space_room(str(room["room_type"]), room_agent_ref):
        raise ValueError("room_not_agent_chat")
    return room, hermes_slug, agent_db_id


def _resolve_agent_room_for_user(
    conn: sqlite3.Connection,
    user_id: str,
    room_id: str,
) -> tuple[sqlite3.Row, str, str]:
    """Agent DM rooms only — infer Hermes slug from room.agent_profile_id."""
    room_id = str(room_id or "").strip()
    user_id = str(user_id or "").strip()
    if not room_id:
        raise ValueError("room_id required")
    if not user_id:
        raise ValueError("authenticated user required")
    if not _user_can_access_room(conn, room_id, user_id):
        raise ValueError("room_access_denied")
    room = conn.execute(
        "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
        (room_id,),
    ).fetchone()
    if not room:
        raise ValueError("room_not_found")
    agent_ref = str(room["agent_profile_id"] or "").strip()
    if not agent_ref:
        raise ValueError("room_not_agent_chat")
    agent_row = _srv()._lookup_agent_profile(conn, str(room["workspace_id"]), agent_ref)
    if not agent_row:
        raise ValueError("agent_profile_not_found")
    return room, str(agent_row["slug"]), str(agent_row["id"])


def _resolve_room_agent_chat(
    conn: sqlite3.Connection,
    user_id: str,
    room_id: str,
) -> tuple[sqlite3.Row, str, str, str, str]:
    """Agent DM bind context from room SSOT — (room, template, runtime, agent_db_id, workspace_id)."""
    user_id = str(user_id or "").strip()
    room_id = str(room_id or "").strip()
    if not user_id or not room_id:
        raise ValueError("room_id and user required")
    if not _user_can_access_room(conn, room_id, user_id):
        raise ValueError("room_access_denied")
    room = conn.execute(
        "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
        (room_id,),
    ).fetchone()
    if not room:
        raise ValueError("room_not_found")
    if _srv()._is_space_room(str(room["room_type"]), room["agent_profile_id"]):
        raise ValueError("room_not_agent_chat")
    agent_ref = str(room["agent_profile_id"] or "").strip()
    if str(room["room_type"]) != "direct" or not agent_ref:
        raise ValueError("room_not_agent_chat")
    workspace_id = str(room["workspace_id"])
    agent_row = _srv()._lookup_agent_profile(conn, workspace_id, agent_ref)
    if not agent_row:
        raise ValueError("agent_profile_not_found")
    template = _srv().resolve_validated_profile(str(agent_row["slug"]))
    runtime = _srv()._resolve_chat_hermes_profile(template, user_id, room_id, workspace_id)
    if not _srv()._runtime_profile_on_disk(runtime) and runtime != template:
        raise ValueError("runtime_profile_not_provisioned")
    return room, template, runtime, str(agent_row["id"]), workspace_id
