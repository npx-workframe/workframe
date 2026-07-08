"""WF-032 extract: credential persistence (vault, auth.json, profile .env overlays)."""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import credential_vault


def _srv():
    import server as srv

    return srv


def _quote_env_value(value: str) -> str:
    raw = str(value or "")
    if re.fullmatch(r"[A-Za-z0-9_./:@+-]+", raw):
        return raw
    return json.dumps(raw)


def _upsert_env_secret(env_path: Path, key: str, value: str) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    found = False
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    updated: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            updated.append(line)
            continue
        current_key, _sep, _rest = line.partition("=")
        if current_key.strip() == key:
            updated.append(f"{key}={_quote_env_value(value)}")
            found = True
        else:
            updated.append(line)
    if not found:
        if updated and updated[-1].strip():
            updated.append("")
        updated.append(f"{key}={_quote_env_value(value)}")
    env_path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")
    _publish_profile_gateway_secrets(env_path.parent.name)


def _publish_profile_gateway_secrets(profile: str) -> None:
    """Hermes gateway runs as uid hermes; API container writes bind-mount files as root.

    Runtime profiles only ever get wf_rt_* lease tokens or auth.json pool metadata —
    never raw upstream keys. chmod so the gateway can read overlays; supervisor still
    blocks agent shell exec against these paths.
    """
    slug = _srv().safe_profile_slug(str(profile or "").strip())
    if not _srv()._is_runtime_profile_slug(slug):
        return
    prof_dir = _srv()._profile_dir(slug)
    for name in (".env", "auth.json"):
        path = prof_dir / name
        if not path.is_file():
            continue
        try:
            os.chmod(path, 0o644)
        except OSError:
            pass


def _upsert_auth_metadata(auth_path: Path, payload: dict[str, Any]) -> None:
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if auth_path.exists():
        try:
            loaded = json.loads(auth_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}
    bindings = data.get("credentials")
    if not isinstance(bindings, list):
        bindings = []
    credential_ref = str(payload.get("credential_ref") or "")
    bindings = [row for row in bindings if not isinstance(row, dict) or row.get("credential_ref") != credential_ref]
    bindings.append({
        "provider": payload.get("provider"),
        "credential_type": payload.get("credential_type"),
        "credential_ref": credential_ref,
        "env_var": payload.get("env_var"),
        "label": payload.get("label") or "",
        "updated_at": payload.get("updated_at"),
    })
    data["credentials"] = bindings
    data["updated_at"] = payload.get("updated_at")
    auth_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _remove_env_secret(env_path: Path, key: str) -> None:
    if not env_path.is_file():
        return
    kept: list[str] = []
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            current_key, _sep, _rest = line.partition("=")
            if current_key.strip() == key:
                continue
        kept.append(line)
    env_path.write_text("\n".join(kept).rstrip() + ("\n" if kept else ""), encoding="utf-8")


def _remove_auth_metadata(auth_path: Path, credential_ref: str) -> None:
    if not auth_path.is_file():
        return
    try:
        loaded = json.loads(auth_path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(loaded, dict):
        return
    bindings = loaded.get("credentials")
    if not isinstance(bindings, list):
        return
    loaded["credentials"] = [
        row for row in bindings
        if not isinstance(row, dict) or str(row.get("credential_ref") or "") != credential_ref
    ]
    loaded["updated_at"] = _srv()._utc_now()
    auth_path.write_text(json.dumps(loaded, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _store_user_credential(
    user_id: str,
    provider: str,
    credential_type: str,
    secret: str,
    env_var: str,
    label: str,
) -> dict[str, Any]:
    user_home = _srv()._user_hermes_home(user_id)
    auth_path = _srv()._user_hermes_auth_path(user_id)
    cred_id = str(uuid.uuid4())
    credential_ref = credential_vault.vault_ref(cred_id)
    now = _srv()._utc_now()
    credential_vault.store_secret(
        cred_id,
        secret,
        env_var=env_var,
        provider=provider,
        scope="user",
        user_id=user_id,
    )
    _remove_env_secret(_srv()._user_hermes_env_path(user_id), env_var)
    _upsert_auth_metadata(
        auth_path,
        {
            "provider": provider,
            "credential_type": credential_type,
            "credential_ref": credential_ref,
            "env_var": env_var,
            "label": label,
            "updated_at": now,
        },
    )
    return {
        "profile_home": str(user_home),
        "credential_id": cred_id,
        "auth_path": str(auth_path),
        "credential_ref": credential_ref,
        "updated_at": now,
    }


def _store_workspace_credential(
    workspace_id: str,
    provider: str,
    credential_type: str,
    secret: str,
    env_var: str,
    label: str,
    created_by: str,
) -> dict[str, Any]:
    """Company-pay keys live on the primary Hermes profile .env (shared stack)."""
    workspace_id = str(workspace_id or "").strip()
    provider = str(provider or "").strip().lower()
    if not workspace_id or not provider or not secret.strip():
        raise ValueError("workspace_credential_invalid")
    spec = _srv()._catalog_provider(provider)
    if spec and spec.get("user_only"):
        raise ValueError("provider_user_only")
    primary = _srv()._primary_profile()
    if not primary:
        raise ValueError("no_primary_profile")
    cred_id = str(uuid.uuid4())
    credential_ref = credential_vault.vault_ref(cred_id)
    now = _srv()._utc_now()
    credential_vault.store_secret(
        cred_id,
        secret.strip(),
        env_var=env_var,
        provider=provider,
        scope="workspace",
        workspace_id=workspace_id,
    )
    _remove_env_secret(_srv()._profile_dir(primary) / ".env", env_var)
    conn = _srv()._workframe_db()
    try:
        existing = conn.execute(
            """SELECT id FROM credential_bindings
               WHERE workspace_id = ? AND provider = ? AND deleted_at IS NULL
               ORDER BY updated_at DESC LIMIT 1""",
            (workspace_id, provider),
        ).fetchone()
        if existing:
            cred_id = str(existing[0])
            conn.execute(
                """UPDATE credential_bindings
                   SET credential_ref = ?, label = ?, is_active = 1, updated_at = ?, deleted_at = NULL
                   WHERE id = ?""",
                (credential_ref, label, now, cred_id),
            )
        else:
            conn.execute(
                """INSERT INTO credential_bindings
                   (id, workspace_id, user_id, agent_profile_id, provider, credential_type,
                    credential_ref, label, is_active, created_by, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cred_id, workspace_id, None, None, provider, credential_type,
                    credential_ref, label, 1, created_by, now, now,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return {
        "credential_id": cred_id,
        "credential_ref": credential_ref,
        "updated_at": now,
    }
