"""User preferences, profile, and onboarding payloads (WF-032)."""
from __future__ import annotations

import json
import re
import sqlite3
import time
from typing import Any

import zk_auth as _zk

from auth_gate import OWNER_ADMIN_ROLES


def _srv():
    import server as srv

    return srv


def parse_user_platform_ids(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("platform_ids must be an object")
    allowed = frozenset({"discord", "telegram", "slack"})
    out: dict[str, str] = {}
    for raw_key, raw_val in value.items():
        key = str(raw_key or "").strip().lower()
        if key not in allowed:
            raise ValueError(f"unsupported platform_id: {raw_key}")
        val = str(raw_val or "").strip()
        if val:
            out[key] = val
    return out


def user_payload(row: sqlite3.Row) -> dict[str, Any]:
    payload = {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "avatar_url": row["avatar_url"],
        "role": row["role"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    keys = set(row.keys())
    if "current_workspace_id" in keys:
        payload["current_workspace_id"] = row["current_workspace_id"]
    if "platform_ids" in keys:
        raw = row["platform_ids"] or "{}"
        try:
            platform_ids = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, json.JSONDecodeError):
            platform_ids = {}
        payload["platform_ids"] = platform_ids if isinstance(platform_ids, dict) else {}
    return payload


def display_name_from_email(email: str) -> str:
    normalized = str(email or "").strip().lower()
    if not normalized or "@" not in normalized:
        return ""
    local_part = normalized.split("@", 1)[0]
    words = [part for part in re.split(r"[._\-\s]+", local_part) if part]
    if not words:
        return ""
    return " ".join(word[:1].upper() + word[1:] for word in words)


def workspace_membership_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "workspace_slug": row["slug"],
        "workspace_display_name": row["display_name"],
        "role": row["role"],
        "status": row["status"],
        "created_at": row["membership_created_at"],
        "updated_at": row["membership_updated_at"],
    }


def get_workframe_user(user_id: str) -> dict[str, Any] | None:
    try:
        db = _srv()._workframe_db()
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        db.close()
        if not row:
            return None
        return user_payload(row)
    except Exception:
        return None


def merge_user_platform_ids(user_id: str, patch: dict[str, str]) -> None:
    user_id = str(user_id or "").strip()
    if not user_id or not patch:
        return
    current: dict[str, str] = {}
    user = get_workframe_user(user_id)
    if user and isinstance(user.get("platform_ids"), dict):
        current = {str(k): str(v) for k, v in user["platform_ids"].items() if str(v or "").strip()}
    merged = {**current, **{str(k): str(v) for k, v in patch.items() if str(v or "").strip()}}
    apply_me_profile_updates(user_id, {"platform_ids": merged})


def read_user_llm_prefs(user_id: str) -> tuple[str, list[dict[str, str]]]:
    user = get_workframe_user(str(user_id or "").strip())
    pids = user.get("platform_ids") if user and isinstance(user.get("platform_ids"), dict) else {}
    primary = str(pids.get("llm_primary") or "").strip()
    chain_raw = pids.get("llm_fallback_chain")
    chain: list[dict[str, str]] = []
    if isinstance(chain_raw, str) and chain_raw.strip():
        try:
            parsed = json.loads(chain_raw)
            if isinstance(parsed, list):
                for entry in parsed:
                    if isinstance(entry, dict):
                        prov = str(entry.get("provider") or "").strip()
                        model = str(entry.get("model") or "").strip()
                        if prov and model:
                            chain.append({"provider": prov, "model": model})
        except json.JSONDecodeError:
            pass
    if not primary and chain:
        first = chain[0]
        prov = str(first.get("provider") or "").strip()
        model = str(first.get("model") or "").strip()
        if model:
            if prov and not model.lower().startswith(f"{prov}/"):
                primary = f"{prov}/{model}"
            else:
                primary = model
    return primary, chain


def write_user_llm_prefs(
    user_id: str,
    *,
    primary: str = "",
    fallback_chain: list[dict[str, str]] | None = None,
) -> None:
    user_id = str(user_id or "").strip()
    if not user_id:
        return
    if not primary and fallback_chain is None:
        return
    user = get_workframe_user(user_id)
    pids: dict[str, Any] = {}
    if user and isinstance(user.get("platform_ids"), dict):
        pids = dict(user["platform_ids"])
    if primary:
        pids["llm_primary"] = primary.strip()
    if fallback_chain is not None:
        pids["llm_fallback_chain"] = json.dumps(fallback_chain, separators=(",", ":"))
    conn = _srv()._workframe_db()
    try:
        conn.execute(
            "UPDATE users SET platform_ids = ?, updated_at = ? WHERE id = ?",
            (json.dumps(pids, sort_keys=True), str(int(time.time())), user_id),
        )
        conn.commit()
    finally:
        conn.close()


def validate_me_profile_updates(updates: dict[str, Any]) -> None:
    avatar = updates.get("avatar_url")
    if avatar is None:
        return
    text = str(avatar).strip()
    if not text:
        return
    if text.startswith("data:") and len(text) > 380_000:
        raise ValueError("Avatar image is too large. Use an image under 256 KB.")
    if len(text) > 400_000:
        raise ValueError("Avatar image is too large. Use an image under 256 KB.")


def apply_me_profile_updates(user_id: str, body: dict[str, Any]) -> dict[str, Any]:
    user_id = str(user_id or "").strip()
    allowed = {"display_name", "avatar_url", "tagline", "bio"}
    updates = {k: v for k, v in body.items() if k in allowed}
    validate_me_profile_updates(updates)
    if "avatar_url" in updates:
        updates["avatar_url"] = _srv()._normalize_user_avatar_url(str(updates.get("avatar_url") or ""))
    profile = _zk.update_profile(user_id, updates) if updates else _zk.get_profile(user_id)
    if "platform_ids" in body:
        platform_ids = parse_user_platform_ids(body.get("platform_ids"))
        conn = _srv()._workframe_db()
        try:
            now_ts = str(int(time.time()))
            conn.execute(
                "UPDATE users SET platform_ids = ?, updated_at = ? WHERE id = ?",
                (json.dumps(platform_ids, sort_keys=True), now_ts, user_id),
            )
            conn.commit()
            workspaces = _srv()._get_user_workspaces(user_id)
            current = _srv()._resolve_current_workspace(user_id, workspaces)
            if current and str(current.get("id") or ""):
                sync_result = _srv()._sync_workspace_messaging_gateway(str(current["id"]))
                if not sync_result.get("ok"):
                    raise ValueError(str(sync_result.get("error") or "messaging_sync_failed"))
        finally:
            conn.close()
    sync_workframe_user_profile(user_id, updates)
    return profile or {}


def sync_workframe_user_profile(user_id: str, fields: dict[str, Any]) -> None:
    user_id = str(user_id or "").strip()
    if not user_id or not fields:
        return
    conn = _srv()._workframe_db()
    try:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return
        sets: list[str] = []
        vals: list[Any] = []
        if "avatar_url" in fields:
            sets.append("avatar_url = ?")
            vals.append(fields["avatar_url"])
        if "display_name" in fields:
            sets.append("display_name = ?")
            vals.append(fields["display_name"])
        if "platform_ids" in fields:
            sets.append("platform_ids = ?")
            vals.append(json.dumps(fields["platform_ids"], sort_keys=True))
        if not sets:
            return
        sets.append("updated_at = ?")
        vals.append(str(int(time.time())))
        vals.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", vals)
        conn.commit()
    finally:
        conn.close()


def current_user_me(user_id: str) -> dict[str, Any]:
    if not user_id:
        return {"ok": False, "error": "no_authenticated_user"}
    try:
        conn = _srv()._workframe_db()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        user = conn.execute(
            """
            SELECT id, email, display_name, avatar_url, role, status, created_at, updated_at
            FROM users
            WHERE id = ? AND deleted_at IS NULL AND status = 'active'
            """,
            (user_id,),
        ).fetchone()
        if not user:
            return {"ok": False, "error": "user_not_found", "user_id": user_id}
        memberships = conn.execute(
            """
            SELECT DISTINCT
                wm.id,
                wm.workspace_id,
                wm.role,
                wm.status,
                wm.created_at AS membership_created_at,
                wm.updated_at AS membership_updated_at,
                w.slug,
                w.display_name
            FROM workspace_memberships wm
            JOIN workspaces w ON w.id = wm.workspace_id
            WHERE wm.user_id = ?
              AND wm.deleted_at IS NULL
              AND wm.status = 'active'
              AND w.deleted_at IS NULL
              AND w.status = 'active'
            ORDER BY w.slug, w.display_name
            """,
            (user_id,),
        ).fetchall()
        return {
            "ok": True,
            "user": user_payload(user),
            "workspace_memberships": [workspace_membership_payload(row) for row in memberships],
        }
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"current_user_lookup_failed: {exc}"}
    finally:
        conn.close()


def onboarding_payload(user_id: str) -> dict[str, Any]:
    user_id = str(user_id or "").strip()
    workspaces = _srv()._get_user_workspaces(user_id)
    ws = next((w for w in workspaces if w.get("slug") == "default"), None) or (workspaces[0] if workspaces else None)
    if not ws:
        return {"ok": True, "complete": False, "step": "workspace", "credential_mode": "byok"}
    ws_id = str(ws.get("id") or "")
    role = str(ws.get("role") or "")
    settings: dict[str, Any] = {}
    try:
        conn = _srv()._workframe_db()
        row = conn.execute(
            "SELECT settings_json FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (ws_id,),
        ).fetchone()
        conn.close()
        if row:
            settings = _srv()._parse_workspace_settings(row)
    except sqlite3.Error:
        pass
    credential_mode = str(settings.get("credential_mode") or "byok").strip() or "byok"
    is_admin = role in OWNER_ADMIN_ROLES
    install_done = _srv()._install_complete()
    integrations_done = bool(settings.get("admin_integrations_done")) or not is_admin or install_done
    admin_done = bool(settings.get("admin_onboarding_done")) or not is_admin or install_done
    user_has_llm = _srv()._user_has_llm_provider(user_id)
    if is_admin and not integrations_done:
        return {
            "ok": True,
            "complete": False,
            "step": "admin_integrations",
            "credential_mode": credential_mode,
            "role": role,
            "workspace_id": ws_id,
        }
    if is_admin and not admin_done:
        return {
            "ok": True,
            "complete": False,
            "step": "admin",
            "credential_mode": credential_mode,
            "role": role,
            "workspace_id": ws_id,
        }
    if credential_mode == "workspace" and is_admin and not _srv()._workspace_has_llm_provider(ws_id):
        return {
            "ok": True,
            "complete": False,
            "step": "workspace_provider",
            "credential_mode": credential_mode,
            "role": role,
            "workspace_id": ws_id,
        }
    if credential_mode == "byok" and not user_has_llm:
        return {
            "ok": True,
            "complete": False,
            "step": "user_provider",
            "credential_mode": credential_mode,
            "role": role,
            "workspace_id": ws_id,
        }
    return {
        "ok": True,
        "complete": True,
        "step": "done",
        "credential_mode": credential_mode,
        "role": role,
        "workspace_id": ws_id,
        "has_llm_provider": user_has_llm,
    }


def session_profile_payload(user_id: str) -> dict[str, Any] | None:
    user_id = str(user_id or "").strip()
    if not user_id:
        return None
    profile = _zk.get_profile(user_id)
    user = get_workframe_user(user_id)
    if not profile and not user:
        return None
    workspaces = _srv()._get_user_workspaces(user_id)
    email = str((user or {}).get("email", "") or "")
    display_name = (
        str((profile or {}).get("display_name", "") or "").strip()
        or str((user or {}).get("display_name", "") or "").strip()
        or display_name_from_email(email)
    )
    default_workspace = next((ws for ws in workspaces if ws.get("slug") == "default"), None)
    current_workspace = _srv()._resolve_current_workspace(user_id, workspaces)
    wf_user = get_workframe_user(user_id) or {}
    platform_ids = wf_user.get("platform_ids") if isinstance(wf_user.get("platform_ids"), dict) else {}
    zk_avatar = str((profile or {}).get("avatar_url") or "").strip()
    wf_avatar = str((user or {}).get("avatar_url") or wf_user.get("avatar_url") or "").strip()
    avatar_url = (
        _srv()._normalize_user_avatar_url(zk_avatar or wf_avatar) if (zk_avatar or wf_avatar) else None
    )
    return {
        "ok": True,
        "user": {
            "user_id": user_id,
            "id": user_id,
            "email": email,
            "display_name": display_name,
            "avatar_url": avatar_url,
            "tagline": (profile or {}).get("tagline"),
            "bio": (profile or {}).get("bio"),
            "platform_ids": platform_ids,
        },
        "workspaces": workspaces,
        "current_workspace": current_workspace,
        "default_workspace": default_workspace,
        "hermes_dashboard_access": _srv()._user_can_access_hermes_dashboard(user_id),
    }
