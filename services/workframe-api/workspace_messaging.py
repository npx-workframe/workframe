"""WF-032 extract: workspace messaging settings and gateway env sync."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

# Hermes gateway reads these from the primary profile .env; vault is source of truth.
_MESSAGING_GATEWAY_ENV: dict[str, dict[str, str]] = {
    "discord": {
        "token": "DISCORD_BOT_TOKEN",
        "home_channel": "DISCORD_HOME_CHANNEL",
        "allowed_users": "DISCORD_ALLOWED_USERS",
    },
    "telegram": {
        "token": "TELEGRAM_BOT_TOKEN",
        "home_channel": "TELEGRAM_HOME_CHANNEL",
        "allowed_users": "TELEGRAM_ALLOWED_USERS",
    },
}


def _srv():
    import server as srv

    return srv


def _parse_messaging_settings_patch(body: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    """Merge admin messaging channel/allowlist config into workspace settings."""
    raw = body.get("messaging")
    if not isinstance(raw, dict):
        return settings
    messaging = settings.get("messaging") if isinstance(settings.get("messaging"), dict) else {}
    merged = dict(messaging)
    for provider in ("discord", "telegram"):
        block = raw.get(provider)
        if not isinstance(block, dict):
            continue
        current = merged.get(provider) if isinstance(merged.get(provider), dict) else {}
        row = dict(current)
        if "home_channel" in block:
            row["home_channel"] = str(block.get("home_channel") or "").strip()
        if "allowed_users" in block:
            row["allowed_users"] = str(block.get("allowed_users") or "").strip()
        merged[provider] = row
    settings["messaging"] = merged
    return settings


def _workspace_member_platform_ids(workspace_id: str) -> dict[str, set[str]]:
    """Collect linked Discord/Telegram user IDs for workspace members."""
    workspace_id = str(workspace_id or "").strip()
    out: dict[str, set[str]] = {"discord": set(), "telegram": set(), "slack": set()}
    if not workspace_id:
        return out
    conn = _srv()._workframe_db()
    try:
        rows = conn.execute(
            """
            SELECT u.platform_ids
            FROM users u
            JOIN workspace_memberships wm ON wm.user_id = u.id
            WHERE wm.workspace_id = ?
              AND wm.deleted_at IS NULL
              AND u.deleted_at IS NULL
              AND wm.status = 'active'
            """,
            (workspace_id,),
        ).fetchall()
    finally:
        conn.close()
    for row in rows:
        raw = row[0] if row else "{}"
        try:
            parsed = json.loads(str(raw or "{}"))
        except (TypeError, json.JSONDecodeError):
            parsed = {}
        if not isinstance(parsed, dict):
            continue
        for platform in out:
            val = str(parsed.get(platform) or "").strip()
            if val:
                out[platform].add(val)
    return out


def _merged_messaging_allowed_users(workspace_id: str, provider: str, seed: str) -> str:
    """Admin seed allowlist + member-linked platform IDs for gateway env."""
    provider = str(provider or "").strip().lower()
    ids: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[\s,;]+", str(seed or "").strip()):
        token = part.strip()
        if token and token not in seen:
            seen.add(token)
            ids.append(token)
    for member_id in sorted(_workspace_member_platform_ids(workspace_id).get(provider, set())):
        if member_id not in seen:
            seen.add(member_id)
            ids.append(member_id)
    return ",".join(ids)


def _workspace_messaging_integrations_payload(workspace_id: str, settings: dict[str, Any]) -> dict[str, Any]:
    messaging = settings.get("messaging") if isinstance(settings.get("messaging"), dict) else {}
    payload: dict[str, Any] = {}
    for provider, env_map in _MESSAGING_GATEWAY_ENV.items():
        block = messaging.get(provider) if isinstance(messaging.get(provider), dict) else {}
        resolved = _srv()._resolve_credential("", workspace_id, provider)
        has_token = bool(resolved and _srv()._credential_secret(resolved, ""))
        payload[provider] = {
            "bot_token_configured": has_token,
            "home_channel": str(block.get("home_channel") or ""),
            "allowed_users": str(block.get("allowed_users") or ""),
        }
    return payload


def _set_primary_messaging_platforms(enabled: dict[str, bool]) -> tuple[bool, str]:
    primary = _srv()._primary_profile()
    if not primary:
        return False, "no_primary_profile"
    flags = {name: bool(enabled.get(name)) for name in ("discord", "telegram")}
    cfg_path = _srv()._profile_gateway_config_path(primary)
    if cfg_path is None:
        return False, "no_primary_profile"
    try:
        import yaml

        cfg: dict[str, Any] = {}
        if cfg_path.is_file():
            loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
            cfg = loaded if isinstance(loaded, dict) else {}
        plats = cfg.setdefault("platforms", {})
        if not isinstance(plats, dict):
            plats = {}
            cfg["platforms"] = plats
        for name, on in flags.items():
            row = plats.get(name) if isinstance(plats.get(name), dict) else {}
            row["enabled"] = bool(on)
            plats[name] = row
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        return True, "ok"
    except (OSError, ImportError) as exc:
        return False, str(exc)


def _sync_workspace_messaging_gateway(workspace_id: str) -> dict[str, Any]:
    """Vault → primary profile .env overlay + platform toggles + gateway restart."""
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return {"ok": False, "error": "workspace_id_required"}
    primary = _srv()._primary_profile()
    if not primary:
        return {"ok": False, "error": "no_primary_profile"}
    try:
        conn = _srv()._workframe_db()
        row = conn.execute(
            "SELECT settings_json FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        conn.close()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"db_error: {exc}"}
    settings = _srv()._parse_workspace_settings(row) if row else {}
    messaging = settings.get("messaging") if isinstance(settings.get("messaging"), dict) else {}
    env_path = _srv()._profile_dir(primary) / ".env"
    enabled: dict[str, bool] = {}
    for provider, env_map in _MESSAGING_GATEWAY_ENV.items():
        token_var = env_map["token"]
        resolved = _srv()._resolve_credential("", workspace_id, provider)
        secret = _srv()._credential_secret(resolved, "") if resolved else ""
        block = messaging.get(provider) if isinstance(messaging.get(provider), dict) else {}
        if secret:
            _srv()._upsert_env_secret(env_path, token_var, secret)
            enabled[provider] = True
            home = str(block.get("home_channel") or "").strip()
            if home:
                _srv()._upsert_env_secret(env_path, env_map["home_channel"], home)
            else:
                _srv()._remove_env_secret(env_path, env_map["home_channel"])
            allowed = _merged_messaging_allowed_users(
                workspace_id,
                provider,
                str(block.get("allowed_users") or ""),
            )
            if allowed:
                _srv()._upsert_env_secret(env_path, env_map["allowed_users"], allowed)
            else:
                _srv()._remove_env_secret(env_path, env_map["allowed_users"])
        else:
            enabled[provider] = False
            for key in env_map.values():
                _srv()._remove_env_secret(env_path, key)
    ok, out = _set_primary_messaging_platforms(enabled)
    if not ok:
        return {"ok": False, "error": f"messaging_platform_config_failed: {out}"}
    try:
        restart = _srv()._restart_stack_gateway()
    except (ValueError, OSError, RuntimeError) as exc:
        _srv()._log_handler_error("_sync_workspace_messaging_gateway restart", exc)
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "gateway": restart}
