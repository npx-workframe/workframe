"""WF-032 extract: credential binding resolution and secret materialization."""

from __future__ import annotations

import re
import sqlite3
import time
from typing import Any

import credential_vault
import provider_catalog


def _srv():
    import server as srv

    return srv


def _default_credential_env_var(provider: str, credential_type: str) -> str:
    prefix = re.sub(r"[^A-Za-z0-9]+", "_", str(provider or "WORKFRAME").strip()).upper() or "WORKFRAME"
    suffix = {
        "bot_token": "BOT_TOKEN",
        "oauth": "OAUTH_TOKEN",
    }.get(str(credential_type or "api_key"), "API_KEY")
    return f"{prefix}_{suffix}"
def _provider_env_var(provider: str) -> str:
    spec = provider_catalog.catalog_provider(provider)
    if spec and str(spec.get("env_var") or "").strip():
        return str(spec["env_var"]).strip()
    return _default_credential_env_var(provider, "api_key")


def _credential_secret(resolved: dict[str, Any], user_id: str = "") -> str:
    ref = str(resolved.get("credential_ref") or "")
    binding_id = credential_vault.parse_vault_ref(ref)
    if binding_id:
        return credential_vault.read_secret(binding_id)
    env_var = str(resolved.get("env_var") or "")
    if not env_var and ref.startswith("env:"):
        env_var = ref[4:]
    if not env_var:
        return ""
    scope = str(resolved.get("scope") or "")
    secret = ""
    if scope == "user":
        user = str(user_id or resolved.get("user_id") or "").strip()
        if user:
            secret = _srv()._read_env_map(_srv()._user_hermes_env_path(user)).get(env_var, "")
            if secret:
                bid = str(resolved.get("credential_binding_id") or resolved.get("credential_id") or "").strip()
                if bid:
                    credential_vault.store_secret(
                        bid,
                        secret,
                        env_var=env_var,
                        provider=str(resolved.get("provider") or ""),
                        scope="user",
                        user_id=user,
                    )
                    _srv()._remove_env_secret(_srv()._user_hermes_env_path(user), env_var)
    elif scope == "workspace":
        secret = _srv()._stack_profile_env().get(env_var, "")
    elif scope == "stack":
        secret = _srv()._stack_profile_env().get(env_var, "")
    return secret


def _resolve_secret_for_lease(
    payer_user_id: str,
    workspace_id: str,
    provider: str,
    binding_id: str,
) -> tuple[str, str]:
    provider = str(provider or "openrouter").strip().lower()
    binding_id = str(binding_id or "").strip()
    if binding_id:
        secret = credential_vault.read_secret(binding_id)
        if secret:
            return _provider_env_var(provider), secret
    resolved = _resolve_credential(payer_user_id, workspace_id, provider, user_only=True)
    if not resolved:
        resolved = _resolve_credential(payer_user_id, workspace_id, provider, user_only=False)
    if not resolved:
        return "", ""
    env_var = str(resolved.get("env_var") or "") or _provider_env_var(provider)
    return env_var, _credential_secret(resolved, payer_user_id)
def _credential_binding_payload(row: sqlite3.Row, scope: str) -> dict[str, Any]:
    """Return the safe metadata payload for a resolved credential binding."""
    return {
        "credential_binding_id": row["id"],
        "credential_id": row["id"],
        "credential_ref": row["credential_ref"],
        "scope": scope,
        "provider": row["provider"],
        "credential_type": row["credential_type"],
        "label": row["label"] or "",
        "user_id": row["user_id"],
        "workspace_id": row["workspace_id"],
        "agent_profile_id": row["agent_profile_id"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "expires_at": row["expires_at"],
    }


def _resolve_credential(
    user_id: str,
    workspace_id: str,
    provider: str,
    *,
    user_only: bool = False,
) -> dict[str, Any] | None:
    """Resolve which credential binding to use for an agent run.

    Resolution order:
    1. User-owned credential for this user + provider (if active and not expired)
    2. Workspace credential for this workspace + provider (if active and not expired)
       â€” skipped when user_only=True (dev/github/vercel tenancy)
    3. None (caller uses profile config fallback)
    """
    user = str(user_id or "").strip()
    workspace = str(workspace_id or "").strip()
    provider_name = str(provider or "").strip().lower()
    if not provider_name or (not user and not workspace):
        return None

    now_iso = _srv()._utc_now()
    now_ts = str(int(time.time()))
    conn = None
    try:
        conn = _srv()._workframe_db()
        conn.row_factory = sqlite3.Row
        if user:
            row = conn.execute(
                """
                SELECT id, workspace_id, user_id, agent_profile_id, provider,
                       credential_type, credential_ref, label, is_active,
                       expires_at, created_by, created_at, updated_at, deleted_at
                FROM credential_bindings
                WHERE user_id = ?
                  AND LOWER(provider) = ?
                  AND is_active = 1
                  AND deleted_at IS NULL
                  AND (expires_at IS NULL OR expires_at > ? OR CAST(expires_at AS INTEGER) > ?)
                ORDER BY updated_at DESC, created_at DESC, id DESC
                LIMIT 1
                """,
                (user, provider_name, now_iso, now_ts),
            ).fetchone()
            if row:
                return _credential_binding_payload(row, "user")

        if workspace and not user_only:
            row = conn.execute(
                """
                SELECT id, workspace_id, user_id, agent_profile_id, provider,
                       credential_type, credential_ref, label, is_active,
                       expires_at, created_by, created_at, updated_at, deleted_at
                FROM credential_bindings
                WHERE workspace_id = ?
                  AND LOWER(provider) = ?
                  AND is_active = 1
                  AND deleted_at IS NULL
                  AND (expires_at IS NULL OR expires_at > ? OR CAST(expires_at AS INTEGER) > ?)
                ORDER BY updated_at DESC, created_at DESC, id DESC
                LIMIT 1
                """,
                (workspace, provider_name, now_iso, now_ts),
            ).fetchone()
            if row:
                return _credential_binding_payload(row, "workspace")
    except sqlite3.Error:
        pass
    finally:
        if conn is not None:
            conn.close()

    if user:
        spec = provider_catalog.catalog_provider(provider_name)
        if spec and str(spec.get("category") or "") == "llm":
            env_var = str(spec.get("env_var") or "").strip()
            if env_var and _srv()._read_env_map(_srv()._user_hermes_env_path(user)).get(env_var):
                return {
                    "credential_binding_id": None,
                    "credential_id": None,
                    "credential_ref": f"env:{env_var}",
                    "scope": "user",
                    "provider": provider_name,
                    "credential_type": str(spec.get("connect_mode") or "api_key"),
                    "label": env_var,
                    "env_var": env_var,
                    "user_id": user,
                    "workspace_id": None,
                    "agent_profile_id": None,
                    "created_by": user,
                    "created_at": None,
                    "updated_at": None,
                    "expires_at": None,
                }
    return None
