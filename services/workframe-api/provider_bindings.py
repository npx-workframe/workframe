"""WF-032 extract: user provider bindings and OAuth LLM connection state."""

from __future__ import annotations

import json
import re
import secrets
import shlex
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import provider_bootstrap
import credential_lifecycle
import credential_vault


def _srv():
    import server as srv

    return srv


_load_profile_auth_json = provider_bootstrap._load_profile_auth_json

_RAW_AUTHORITY_KEYS = frozenset({
    "access_token", "refresh_token", "authorization_code", "id_token", "api_key", "client_secret"
})


def _runtime_auth_contains_raw_authority(value: Any) -> bool:
    """Return true when runtime auth metadata contains reusable upstream authority."""
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in _RAW_AUTHORITY_KEYS and str(child or "").strip():
                return True
            if _runtime_auth_contains_raw_authority(child):
                return True
    elif isinstance(value, list):
        return any(_runtime_auth_contains_raw_authority(child) for child in value)
    return False


def _scan_runtime_auth_files(root: Path) -> list[dict[str, str]]:
    """Scan runtime auth metadata without returning any secret values."""
    findings: list[dict[str, str]] = []
    base = Path(root)
    if not base.is_dir():
        return findings
    for path in sorted(base.rglob("auth.json")):
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            findings.append({"path": str(path), "kind": "malformed"})
            continue
        if not isinstance(parsed, dict):
            findings.append({"path": str(path), "kind": "malformed"})
        elif _runtime_auth_contains_raw_authority(parsed):
            findings.append({"path": str(path), "kind": "raw_authority"})
    return findings

def _user_provider_bindings(user_id: str) -> dict[str, dict[str, Any]]:
    by_provider: dict[str, dict[str, Any]] = {}
    try:
        conn = sqlite3.connect(str(_srv()._workframe_db_path()), timeout=3.0)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT id, provider, credential_type, credential_ref, label, is_active, updated_at
               FROM credential_bindings
               WHERE user_id = ? AND deleted_at IS NULL AND is_active = 1
               ORDER BY updated_at DESC, created_at DESC""",
            (user_id,),
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        rows = []
    for row in rows:
        provider = str(row["provider"] or "").lower()
        if provider and provider not in by_provider:
            by_provider[provider] = dict(row)
    return by_provider


def _workspace_provider_bindings(workspace_id: str) -> dict[str, dict[str, Any]]:
    """Return the active, newest shared credential for each workspace provider."""
    by_provider: dict[str, dict[str, Any]] = {}
    try:
        conn = sqlite3.connect(str(_srv()._workframe_db_path()), timeout=3.0)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT id, provider, credential_type, credential_ref, label, is_active, updated_at
               FROM credential_bindings
               WHERE workspace_id = ? AND user_id IS NULL
                 AND deleted_at IS NULL AND is_active = 1
               ORDER BY updated_at DESC, created_at DESC""",
            (workspace_id,),
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        rows = []
    for row in rows:
        provider = str(row["provider"] or "").lower()
        if provider and provider not in by_provider:
            by_provider[provider] = dict(row)
    return by_provider


_DEVICE_OAUTH_PROVIDER_IDS: frozenset[str] = frozenset({"codex", "nous"})
_oauth_device_lock = threading.Lock()
_oauth_device_sessions: dict[str, dict[str, Any]] = {}

# Public Codex CLI OAuth client used by Hermes (`nousresearch/hermes-agent`).
CODEX_OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_OAUTH_BASE_URL = "https://chatgpt.com/backend-api/codex"
CODEX_OAUTH_AUTH_TYPE = "oauth_external"
_OAUTH_ACCESS_FIELDS = ("access_token", "accessToken")
_OAUTH_REFRESH_FIELDS = ("refresh_token", "refreshToken")


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", str(text or ""))


def _hermes_auth_id_for_spec(spec: dict[str, Any]) -> str:
    return str(spec.get("hermes_auth_id") or spec.get("id") or "").strip()


def _hermes_oauth_auth_keys(hermes_auth_id: str) -> set[str]:
    raw = str(hermes_auth_id or "").strip().lower()
    if not raw:
        return set()
    keys = {raw, raw.replace("-", ""), raw.replace("-", "_")}
    if "-" in raw:
        keys.add(raw.split("-")[-1])
    return {key for key in keys if key}


def _oauth_llm_provider_spec(provider: str) -> dict[str, Any] | None:
    spec = _srv()._catalog_provider_for_llm(provider)
    if spec and str(spec.get("connect_mode") or "") == "oauth":
        return spec
    return None


def _auth_json_has_oauth_material(data: dict[str, Any]) -> bool:
    providers = data.get("providers")
    if isinstance(providers, dict) and providers:
        return True
    pool = data.get("credential_pool")
    if isinstance(pool, dict) and any(isinstance(entries, list) and entries for entries in pool.values()):
        return True
    creds = data.get("credentials")
    return isinstance(creds, list) and bool(creds)


def _codex_oauth_provider(provider_id: str, hermes_auth_id: str = "") -> bool:
    keys = {str(provider_id or "").strip().lower(), str(hermes_auth_id or "").strip().lower()}
    return bool(keys & {"codex", "openai-codex", "openai_codex"})


def _oauth_source_dicts(entry: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    tokens = entry.get("tokens")
    if isinstance(tokens, dict):
        sources.append(tokens)
    sources.append(entry)
    return sources


def _oauth_field(entry: dict[str, Any], names: tuple[str, ...]) -> str:
    for source in _oauth_source_dicts(entry):
        for name in names:
            value = str(source.get(name) or "").strip()
            if value:
                return value
    return ""


def _oauth_entry_has_tokens(entry: dict[str, Any]) -> bool:
    return bool(
        _oauth_field(entry, _OAUTH_ACCESS_FIELDS)
        or _oauth_field(entry, _OAUTH_REFRESH_FIELDS)
    )


def _iter_oauth_auth_entries(loaded: dict[str, Any], hermes_auth_id: str):
    keys = _hermes_oauth_auth_keys(hermes_auth_id)
    providers = loaded.get("providers")
    if isinstance(providers, dict):
        for key, entry in providers.items():
            if str(key).lower() in keys and isinstance(entry, dict):
                yield entry
    creds = loaded.get("credentials")
    if isinstance(creds, list):
        for row in creds:
            if not isinstance(row, dict):
                continue
            pid = str(row.get("provider") or row.get("id") or "").lower()
            if pid in keys:
                yield row
    pool = loaded.get("credential_pool")
    if isinstance(pool, dict):
        for key, entries in pool.items():
            if str(key).lower() not in keys or not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, dict):
                    yield entry


def _extract_oauth_block_from_auth(loaded: dict[str, Any], hermes_auth_id: str) -> dict[str, Any] | None:
    first: dict[str, Any] | None = None
    for entry in _iter_oauth_auth_entries(loaded, hermes_auth_id):
        if _oauth_entry_has_tokens(entry):
            return entry
        if first is None and entry:
            first = entry
    return first


def _extract_oauth_token_material(loaded: dict[str, Any] | None, hermes_auth_id: str) -> dict[str, Any] | None:
    if not isinstance(loaded, dict):
        return None
    for entry in _iter_oauth_auth_entries(loaded, hermes_auth_id):
        access = _oauth_field(entry, _OAUTH_ACCESS_FIELDS)
        refresh = _oauth_field(entry, _OAUTH_REFRESH_FIELDS)
        if access or refresh:
            return {"entry": entry, "access_token": access, "refresh_token": refresh}
    return None


def _build_oauth_vault_bundle(provider_id: str, hermes_auth_id: str, material: dict[str, Any]) -> dict[str, Any]:
    entry = material.get("entry") if isinstance(material.get("entry"), dict) else {}
    token_url = _oauth_field(entry, ("token_url", "tokenUrl"))
    client_id = _oauth_field(entry, ("client_id", "clientId"))
    if _codex_oauth_provider(provider_id, hermes_auth_id):
        token_url = token_url or CODEX_OAUTH_TOKEN_URL
        client_id = client_id or CODEX_OAUTH_CLIENT_ID
    expires_raw = entry.get("expires_at")
    if expires_raw in (None, ""):
        expires_raw = entry.get("expiresAt")
    tokens = entry.get("tokens") if isinstance(entry.get("tokens"), dict) else {}
    if expires_raw in (None, "") and isinstance(tokens, dict):
        expires_raw = tokens.get("expires_at") or tokens.get("expiresAt")
    expires_at: float | None = None
    try:
        if expires_raw not in (None, ""):
            expires_at = float(expires_raw)
    except (TypeError, ValueError):
        expires_at = None
    bundle: dict[str, Any] = {
        "kind": "oauth",
        "provider": provider_id,
        "access_token": str(material.get("access_token") or ""),
        "refresh_token": str(material.get("refresh_token") or ""),
        "token_type": _oauth_field(entry, ("token_type", "tokenType")) or "bearer",
        "token_url": token_url,
        "client_id": client_id,
        "authority": entry,
    }
    if expires_at:
        bundle["expires_at"] = expires_at
    return bundle


def _merge_oauth_auth_into_profile(
    auth: dict[str, Any],
    user_auth: dict[str, Any],
    hermes_auth_id: str,
) -> bool:
    keys = _hermes_oauth_auth_keys(hermes_auth_id)
    changed = False
    block = _extract_oauth_block_from_auth(user_auth, hermes_auth_id)
    if isinstance(block, dict):
        merged = auth.get("providers") if isinstance(auth.get("providers"), dict) else {}
        merged[hermes_auth_id] = block
        auth["providers"] = merged
        changed = True
    user_pool = user_auth.get("credential_pool")
    if isinstance(user_pool, dict):
        pool = auth.get("credential_pool")
        if not isinstance(pool, dict):
            pool = {}
            auth["credential_pool"] = pool
        for key, entries in user_pool.items():
            if str(key).lower() in keys and isinstance(entries, list) and entries:
                for entry in entries:
                    if isinstance(entry, dict) and entry:
                        pool[hermes_auth_id] = [entry]
                        changed = True
                        break
    return changed


def _scrub_oauth_auth_material(auth: dict[str, Any], hermes_auth_id: str) -> bool:
    """Remove reusable OAuth material from runtime auth metadata.

    Refresh tokens stay vault-only. Turn overlay republishes an access-token-only
    credential_pool row for the duration of a run, then scrubs again.
    """
    keys = _hermes_oauth_auth_keys(hermes_auth_id)
    changed = False
    providers = auth.get("providers")
    if isinstance(providers, dict):
        for key in list(providers):
            if str(key).lower() in keys:
                providers.pop(key, None)
                changed = True
    pool = auth.get("credential_pool")
    if isinstance(pool, dict):
        for key in list(pool):
            if str(key).lower() in keys:
                pool.pop(key, None)
                changed = True
    credentials = auth.get("credentials")
    if isinstance(credentials, list):
        kept = []
        for row in credentials:
            provider = str(row.get("provider") or row.get("id") or "").lower() if isinstance(row, dict) else ""
            if provider in keys:
                changed = True
                continue
            kept.append(row)
        if changed:
            auth["credentials"] = kept
    return changed


def _quarantine_legacy_oauth(user_id: str, provider_id: str, auth: dict[str, Any]) -> str:
    """Move legacy runtime OAuth material into the server vault before scrub."""
    spec = _srv()._catalog_provider(provider_id) or {}
    auth_id = _hermes_auth_id_for_spec(spec) or str(provider_id or "").strip()
    block = _extract_oauth_block_from_auth(auth, auth_id)
    if not isinstance(block, dict):
        return ""
    binding_id = str(secrets.token_hex(16))
    try:
        credential_vault.store_secret(
            binding_id,
            json.dumps({"kind": "legacy_oauth", "provider": provider_id, "authority": block}, sort_keys=True),
            provider=str(provider_id or "").strip().lower(),
            scope="user",
            user_id=user_id,
        )
        conn = sqlite3.connect(str(_srv()._workframe_db_path()), timeout=3.0)
        now = _srv()._utc_now()
        conn.execute(
            """INSERT INTO credential_bindings
               (id, workspace_id, user_id, agent_profile_id, provider, credential_type,
                credential_ref, label, is_active, lifecycle_state, created_by, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (binding_id, None, user_id, None, str(provider_id).lower(), "oauth",
             credential_vault.vault_ref(binding_id), f"Quarantined {auth_id}", 0, "quarantined", user_id, now, now),
        )
        conn.commit()
        conn.close()
        return binding_id
    except (OSError, RuntimeError, sqlite3.Error, ValueError):
        try:
            credential_vault.delete_secret(binding_id)
        except Exception:
            pass
        return ""


def _sync_oauth_llm_to_profile(profile: str, user_id: str, provider: str) -> bool:
    spec = _oauth_llm_provider_spec(provider)
    if not spec:
        return False
    hermes_auth_id = _hermes_auth_id_for_spec(spec)
    prof = _srv().resolve_hermes_profile(profile)
    auth = _load_profile_auth_json(prof)
    auth_path = _srv()._profile_dir(prof) / "auth.json"
    before = json.dumps(auth, sort_keys=True, separators=(",", ":"))
    if not _scrub_oauth_auth_material(auth, hermes_auth_id):
        return False
    after = json.dumps(auth, sort_keys=True, separators=(",", ":"))
    if after == before:
        return False
    auth["version"] = 1
    auth["updated_at"] = _srv()._utc_now()
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(json.dumps(auth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _srv()._publish_profile_gateway_secrets(prof)
    return False


def _hermes_oauth_tokens_present(user_id: str, hermes_auth_id: str) -> bool:
    """True when Hermes auth.json has live OAuth tokens for a provider."""
    hermes_auth_id = str(hermes_auth_id or "").strip()
    if not hermes_auth_id:
        return False
    return _extract_oauth_token_material(_load_user_hermes_auth(user_id), hermes_auth_id) is not None


def _load_user_hermes_auth(user_id: str) -> dict[str, Any] | None:
    auth_path = _srv()._user_hermes_auth_path(user_id)
    loaded: dict[str, Any] | None = None
    if auth_path.is_file():
        try:
            data = json.loads(auth_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                loaded = data
        except (OSError, json.JSONDecodeError):
            loaded = None
    if isinstance(loaded, dict) and _auth_json_has_oauth_material(loaded):
        return loaded
    rel = f"profiles/{_srv()._user_hermes_dir_slug(user_id)}/auth.json"
    text = _read_gateway_data_file(rel)
    if text.strip():
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return loaded


def _read_gateway_data_file(rel_path: str) -> str:
    rel_path = str(rel_path or "").strip().lstrip("/")
    if not rel_path or ".." in rel_path.split("/"):
        return ""
    host_path = _srv().HERMES_DATA / rel_path
    if host_path.is_file():
        try:
            return host_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
    if _srv().SECURE_MODE and _srv()._supervisor_ready():
        from profile_secret_policy import gateway_data_file_read_allowed

        if gateway_data_file_read_allowed(rel_path):
            try:
                status, data = _srv()._supervisor_request(
                    "POST",
                    "/v1/gateway.read_data_file",
                    {"rel_path": rel_path},
                    timeout=15.0,
                )
                if status < 300 and isinstance(data, dict) and data.get("ok"):
                    return str(data.get("content") or "")
            except Exception:
                pass
    full = f"/opt/data/{rel_path}"
    try:
        code, out = _srv()._gateway_container_exec(["cat", full])
        return out if code == 0 else ""
    except Exception:
        return ""


def _user_provider_connected(user_id: str, spec: dict[str, Any]) -> bool:
    """Connected = this user's credential resolves with a live secret (no stack/install bleed)."""
    provider_id = str(spec["id"])
    if str(spec.get("connect_mode") or "") == "oauth":
        resolved = _srv()._resolve_credential(user_id, "", provider_id, user_only=True)
        secret = _srv()._credential_secret(resolved, user_id) if resolved else ""
        if not secret:
            return False
        import credential_broker
        bundle = credential_broker._oauth_bundle(secret)
        return bool(
            bundle
            and (
                str(bundle.get("access_token") or "").strip()
                or str(bundle.get("refresh_token") or "").strip()
            )
        )
    if str(spec.get("category") or "") == "llm":
        resolved = _srv()._resolve_credential(user_id, "", provider_id, user_only=True)
        return bool(resolved and _srv()._credential_secret(resolved, user_id))
    bindings = _user_provider_bindings(user_id)
    env_keys = _srv()._user_auth_env_keys(user_id)
    return _srv()._provider_connected_for_user(user_id, spec, bindings, env_keys)


def list_user_providers(
    user_id: str,
    workspace_id: str = "",
    credential_scope: str = "effective",
) -> dict[str, Any]:
    scope = str(credential_scope or "effective").strip().lower()
    if scope not in {"effective", "user", "workspace"}:
        scope = "effective"
    bindings = _user_provider_bindings(user_id)
    workspace = str(workspace_id or "").strip()
    workspace_bindings = _workspace_provider_bindings(workspace) if workspace else {}
    workspace_mode = bool(workspace and _srv()._workspace_credential_mode(None, workspace) == "workspace")
    providers: list[dict[str, Any]] = []
    for spec in _srv().PROVIDER_CONNECT_CATALOG:
        provider_id = str(spec["id"])
        env_var = str(spec.get("env_var") or "")
        binding = bindings.get(provider_id)
        workspace_binding = workspace_bindings.get(provider_id)
        connected = False
        source: str | None = None
        selected_binding: dict[str, Any] | None = None
        if scope == "workspace":
            selected_binding = workspace_binding
            if selected_binding:
                connected = bool(_srv()._credential_secret(selected_binding, user_id))
                source = "workspace" if connected else None
        else:
            connected = _user_provider_connected(user_id, spec)
            source = "user" if connected else None
            selected_binding = binding if connected else None
            if (
                scope == "effective"
                and not connected
                and workspace_mode
                and str(spec.get("category") or "") == "llm"
                and workspace_binding
            ):
                connected = bool(_srv()._credential_secret(workspace_binding, user_id))
                if connected:
                    source = "workspace"
                    selected_binding = workspace_binding
        oauth_configured = None
        if str(spec.get("connect_mode") or "") == "oauth":
            oauth_name = str(spec.get("oauth_provider") or provider_id)
            if oauth_name == "github":
                oauth_configured = _srv()._github_oauth_configured(workspace_id)
            elif oauth_name == "stripe":
                oauth_configured = _srv()._stripe_connect_configured()
        providers.append({
            **spec,
            "connected": connected,
            "source": source,
            "credential_id": str(selected_binding["id"]) if selected_binding else None,
            "credential_ref": str(selected_binding["credential_ref"]) if selected_binding else (f"env:{env_var}" if env_var and connected else None),
            "profile_home": str(_srv()._user_hermes_home(user_id)),
            "oauth_configured": oauth_configured,
            "user_only": bool(spec.get("user_only")),
        })
    return {
        "ok": True,
        "credential_scope": scope,
        "providers": providers,
        "profile_home": str(_srv()._user_hermes_home(user_id)),
    }


def disconnect_user_credential(user_id: str, credential_id: str) -> dict[str, Any]:
    try:
        conn = sqlite3.connect(str(_srv()._workframe_db_path()), timeout=3.0)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """SELECT id, provider, credential_type, credential_ref
               FROM credential_bindings
               WHERE id = ? AND user_id = ? AND deleted_at IS NULL""",
            (credential_id, user_id),
        ).fetchone()
        if not row:
            conn.close()
            return {"ok": False, "error": "credential_not_found"}
        cred_ref = str(row["credential_ref"] or "")
        env_var = cred_ref[4:] if cred_ref.startswith("env:") else ""
        if not env_var:
            spec = _srv()._catalog_provider(str(row["provider"]))
            env_var = str((spec or {}).get("env_var") or "")
        if env_var:
            _srv()._remove_env_secret(_srv()._user_hermes_env_path(user_id), env_var)
            _srv()._remove_auth_metadata(_srv()._user_hermes_auth_path(user_id), cred_ref or f"env:{env_var}")
        conn.close()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"db_error: {exc}"}
    if not credential_lifecycle.revoke_binding(credential_id, reason="user_disconnect"):
        return {"ok": False, "error": "credential_revoke_failed"}
    _srv()._revoke_runtime_llm_leases(
        payer_user_id=user_id,
        provider=str(row["provider"]),
        credential_binding_id=credential_id,
    )
    return {"ok": True, "credential_id": credential_id, "provider": str(row["provider"])}


def _remove_hermes_oauth_provider(user_id: str, hermes_auth_id: str) -> None:
    hermes_auth_id = str(hermes_auth_id or "").strip()
    if not hermes_auth_id:
        return
    auth_path = _srv()._user_hermes_auth_path(user_id)
    if auth_path.is_file():
        try:
            loaded = json.loads(auth_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # A malformed auth file is a visible quarantine condition. Never
            # replace it with an empty object as part of disconnect cleanup.
            loaded = None
        if isinstance(loaded, dict):
            providers = loaded.get("providers")
            if isinstance(providers, dict):
                for key in list(providers.keys()):
                    if key.lower() in {hermes_auth_id.lower(), hermes_auth_id.replace("-", "").lower()}:
                        providers.pop(key, None)
            pool = loaded.get("credential_pool")
            if isinstance(pool, dict):
                for key in list(pool.keys()):
                    if key.lower() in {hermes_auth_id.lower(), hermes_auth_id.replace("-", "").lower()}:
                        pool.pop(key, None)
            loaded["updated_at"] = _srv()._utc_now()
            auth_path.write_text(json.dumps(loaded, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    user_part = re.sub(r"[^a-z0-9]+", "-", _srv()._user_hermes_dir_slug(user_id).lower()).strip("-")[:20] or "user"
    prefix = f"u-{user_part}-"
    profiles_dir = _srv().HERMES_DATA / "profiles"
    if profiles_dir.is_dir():
        for prof_dir in profiles_dir.iterdir():
            if not prof_dir.is_dir() or not prof_dir.name.startswith(prefix):
                continue
            prof_auth = prof_dir / "auth.json"
            if not prof_auth.is_file():
                continue
            try:
                pdata = json.loads(prof_auth.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(pdata, dict):
                continue
            pproviders = pdata.get("providers")
            if isinstance(pproviders, dict):
                for key in list(pproviders.keys()):
                    if key.lower() in {hermes_auth_id.lower(), hermes_auth_id.replace("-", "").lower()}:
                        pproviders.pop(key, None)
                pdata["updated_at"] = _srv()._utc_now()
                prof_auth.write_text(json.dumps(pdata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def disconnect_user_provider(user_id: str, provider_id: str) -> dict[str, Any]:
    spec = _srv()._catalog_provider(provider_id)
    if not spec:
        return {"ok": False, "error": "provider_not_found"}
    env_var = str(spec.get("env_var") or "")
    if env_var:
        _srv()._remove_env_secret(_srv()._user_hermes_env_path(user_id), env_var)
        _srv()._remove_auth_metadata(_srv()._user_hermes_auth_path(user_id), f"env:{env_var}")
    if str(spec.get("connect_mode") or "") == "oauth":
        _remove_hermes_oauth_provider(user_id, _hermes_auth_id_for_spec(spec))
    binding = _user_provider_bindings(user_id).get(str(spec["id"]))
    if binding:
        return disconnect_user_credential(user_id, str(binding["id"]))
    return {"ok": True, "provider": provider_id, "disconnected": True}


def _hermes_user_shell(user_id: str, script: str, *, timeout: float = 30.0) -> tuple[int, str]:
    home = _srv()._hermes_user_home_container(user_id)
    _srv()._user_hermes_home(user_id).mkdir(parents=True, exist_ok=True)
    shell = (
        f"export HERMES_HOME={shlex.quote(home)} HOME={shlex.quote(home)}; "
        f"mkdir -p {shlex.quote(home)}; cd {shlex.quote(home)}; {script}"
    )
    if _srv().SECURE_MODE:
        if not _srv()._supervisor_ready():
            raise RuntimeError(
                "Docker socket access is disabled in _srv().SECURE_MODE; "
                "configure WORKFRAME_SUPERVISOR_URL and WORKFRAME_SUPERVISOR_TOKEN"
            )
        status, data = _srv()._supervisor_request(
            "POST",
            "/v1/gateway.container_exec",
            {"args": ["sh", "-lc", shell]},
            timeout=timeout,
        )
        if status >= 300:
            err = data.get("error") if isinstance(data, dict) else str(data)
            raise ValueError(err or f"supervisor gateway.container_exec failed ({status})")
        if not isinstance(data, dict):
            raise ValueError("supervisor gateway.container_exec returned invalid payload")
        exit_code = data.get("exit_code")
        try:
            code = int(exit_code if exit_code is not None else 1)
        except (TypeError, ValueError):
            code = 1
        return code, str(data.get("output") or "")
    return _srv()._docker_exec(_srv().GATEWAY_CONTAINER_NAME, ["sh", "-lc", shell])


def _parse_device_oauth_log(text: str) -> dict[str, str | None]:
    clean = _strip_ansi(text)
    verification_uri = None
    for match in re.finditer(r"https?://[^\s\]\)>\"']+", clean):
        url = match.group(0).rstrip(".,;)")
        if any(token in url.lower() for token in ("/device", "/portal", "auth.openai.com", "nousresearch")):
            verification_uri = url
            break
    if not verification_uri:
        url_match = re.search(
            r"Open this URL.*?\n\s*(\S+)",
            clean,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if url_match:
            verification_uri = url_match.group(1).strip()
    user_code = None
    code_match = re.search(
        r"Enter this code.*?\n\s*(\S+)",
        clean,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if code_match:
        user_code = code_match.group(1).strip()
    if not user_code:
        bare = re.search(r"\b([A-Z0-9]{4,8}-[A-Z0-9]{4,8})\b", clean)
        if bare:
            user_code = bare.group(1)
    return {"verification_uri": verification_uri, "user_code": user_code}


def _device_oauth_error_from_log(log_text: str) -> str | None:
    clean = _strip_ansi(log_text).strip()
    if not clean:
        return None
    lowered = clean.lower()
    if "rate-limit" in lowered or "rate limiting" in lowered or "http 429" in lowered or re.search(r"\b429\b", lowered):
        return (
            "OpenAI is rate-limiting Codex login requests (HTTP 429). "
            "Wait a minute and try again."
        )
    auth_err = re.search(r"AuthError:\s*(.+)", clean)
    if auth_err:
        return auth_err.group(1).strip()[:500]
    if any(token in lowered for token in ("login timed out", "login cancelled", "oauth_start_failed")):
        lines = [line.strip() for line in clean.splitlines() if line.strip()]
        return (lines[-1] if lines else "OAuth failed")[:500]
    if "traceback" in lowered and any(token in lowered for token in ("error", "exception", "failed")):
        for line in reversed(clean.splitlines()):
            stripped = line.strip()
            if not stripped or stripped.startswith("File ") or "Traceback" in stripped:
                continue
            if stripped.endswith(":") and "Error" not in stripped:
                continue
            return stripped[:500]
    return None


def _sync_user_oauth_provider_to_runtime_profiles(user_id: str, hermes_auth_id: str) -> None:
    # OAuth refresh/access material must never be copied into runtime profiles.
    # Existing material is scrubbed during the migration/connection path.
    user_auth_path = _srv()._user_hermes_auth_path(user_id)
    if user_auth_path.is_file():
        try:
            user_auth = json.loads(user_auth_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            user_auth = None
        if isinstance(user_auth, dict) and _scrub_oauth_auth_material(user_auth, hermes_auth_id):
            user_auth["updated_at"] = _srv()._utc_now()
            user_auth_path.write_text(json.dumps(user_auth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    user_part = re.sub(r"[^a-z0-9]+", "-", _srv()._user_hermes_dir_slug(user_id).lower()).strip("-")[:20] or "user"
    prefix = f"u-{user_part}-"
    profiles_dir = _srv().HERMES_DATA / "profiles"
    if not profiles_dir.is_dir():
        return
    for prof_dir in profiles_dir.iterdir():
        if not prof_dir.is_dir() or not prof_dir.name.startswith(prefix):
            continue
        auth_path = prof_dir / "auth.json"
        auth = _load_profile_auth_json(prof_dir.name)
        if not _scrub_oauth_auth_material(auth, hermes_auth_id):
            continue
        auth["version"] = 1
        auth["updated_at"] = _srv()._utc_now()
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        auth_path.write_text(json.dumps(auth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _srv()._publish_profile_gateway_secrets(prof_dir.name)


def _publish_turn_oauth_access(
    profile: str,
    provider: str,
    access_token: str,
    authority: dict[str, Any] | None = None,
) -> bool:
    """Publish an access-token-only credential_pool row for Hermes native OAuth."""
    access_token = str(access_token or "").strip()
    if not access_token:
        return False
    spec = _oauth_llm_provider_spec(provider) or _srv()._catalog_provider(provider) or {}
    hermes_auth_id = _hermes_auth_id_for_spec(spec) or str(provider or "").strip()
    if not hermes_auth_id:
        return False
    prof = _srv().resolve_hermes_profile(profile)
    auth = _load_profile_auth_json(prof)
    auth_path = _srv()._profile_dir(prof) / "auth.json"
    pool = auth.get("credential_pool")
    if not isinstance(pool, dict):
        pool = {}
        auth["credential_pool"] = pool
    authority = authority if isinstance(authority, dict) else {}
    auth_type = str(authority.get("auth_type") or authority.get("authType") or "").strip()
    base_url = str(authority.get("base_url") or authority.get("baseUrl") or "").strip()
    label = str(authority.get("label") or "").strip()
    entry_id = str(authority.get("id") or "").strip() or "workframe-turn"
    if _codex_oauth_provider(provider, hermes_auth_id):
        auth_type = auth_type or CODEX_OAUTH_AUTH_TYPE
        base_url = base_url or CODEX_OAUTH_BASE_URL
        label = label or "Codex"
    entry = {
        "id": entry_id,
        "label": label or hermes_auth_id,
        "auth_type": auth_type or "oauth",
        "access_token": access_token,
    }
    if base_url:
        entry["base_url"] = base_url
    pool[hermes_auth_id] = [entry]
    auth["version"] = 1
    auth["updated_at"] = _srv()._utc_now()
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(json.dumps(auth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _srv()._publish_profile_gateway_secrets(prof)
    return True


def _scrub_profile_oauth_auth(profile: str) -> bool:
    """Scrub reusable OAuth LLM material from one runtime profile auth.json."""
    try:
        prof = _srv().resolve_hermes_profile(profile)
    except ValueError:
        return False
    auth = _load_profile_auth_json(prof)
    auth_path = _srv()._profile_dir(prof) / "auth.json"
    changed = False
    for spec in _srv().PROVIDER_CONNECT_CATALOG:
        if str(spec.get("connect_mode") or "") != "oauth":
            continue
        if str(spec.get("category") or "") != "llm":
            continue
        auth_id = _hermes_auth_id_for_spec(spec)
        if auth_id and _scrub_oauth_auth_material(auth, auth_id):
            changed = True
    if not changed:
        return False
    auth["version"] = 1
    auth["updated_at"] = _srv()._utc_now()
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(json.dumps(auth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _srv()._publish_profile_gateway_secrets(prof)
    return True


def _finalize_hermes_device_oauth(user_id: str, provider_id: str, spec: dict[str, Any]) -> None:
    hermes_auth_id = _hermes_auth_id_for_spec(spec)
    _sync_user_oauth_provider_to_runtime_profiles(user_id, hermes_auth_id)
    # The picker caches connected providers for one minute. Clear it after
    # vault adopt so the completed Codex connection is visible immediately.
    _srv()._invalidate_user_llm_picker_cache(user_id)
    return None


def _connected_device_oauth_payload(
    user_id: str,
    provider_id: str,
    session_id: str,
    *,
    credential_id: str = "",
    verification_uri: Any = None,
    user_code: Any = None,
) -> dict[str, Any]:
    payload = {
        "ok": True,
        "provider": provider_id,
        "session_id": session_id,
        "status": "connected",
        "connected": True,
        "verification_uri": verification_uri,
        "user_code": user_code,
    }
    if credential_id:
        payload["credential_id"] = credential_id
    return payload


def _adopt_hermes_device_oauth(
    user_id: str,
    provider_id: str,
    spec: dict[str, Any],
    session_id: str,
    workspace_id: str = "",
) -> dict[str, Any]:
    """Move completed device OAuth tokens into the vault as a connected provider."""
    hermes_auth_id = _hermes_auth_id_for_spec(spec)
    material = _extract_oauth_token_material(_load_user_hermes_auth(user_id), hermes_auth_id)
    if not material:
        return _oauth_broker_unsupported(user_id, provider_id, spec, session_id)
    bundle = _build_oauth_vault_bundle(provider_id, hermes_auth_id, material)
    env_var = str(spec.get("env_var") or "")
    entry = material.get("entry") if isinstance(material.get("entry"), dict) else {}
    label = str(entry.get("label") or "").strip() or f"{spec.get('label') or provider_id} OAuth"
    try:
        payload = _srv()._store_user_credential(
            user_id,
            provider_id,
            "oauth",
            json.dumps(bundle, sort_keys=True),
            env_var,
            label,
        )
        cred_id = str(payload["credential_id"])
        _srv()._credential_lifecycle_revoke_other_bindings(
            user_id=user_id,
            provider=provider_id,
            keep_id=cred_id,
            reason="oauth_replacement",
        )
    except (OSError, RuntimeError, sqlite3.Error, ValueError):
        _device_oauth_session_patch(session_id, {"status": "error", "finalized": False})
        return {
            "ok": False,
            "provider": provider_id,
            "session_id": session_id,
            "status": "error",
            "error": "oauth_adopt_failed",
            "message": "OAuth completed upstream, but Workframe could not store the vault-backed provider.",
        }
    _finalize_hermes_device_oauth(user_id, provider_id, spec)
    _srv()._bootstrap_model_after_llm_connect(user_id, workspace_id, provider_id)
    _device_oauth_session_patch(session_id, {"status": "connected", "finalized": True})
    return _connected_device_oauth_payload(
        user_id,
        provider_id,
        session_id,
        credential_id=cred_id,
    )


def _oauth_broker_unsupported(user_id: str, provider_id: str, spec: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Return a stable failure after scrubbing a token-bearing Hermes auth file."""
    legacy = _load_user_hermes_auth(user_id)
    if isinstance(legacy, dict):
        quarantined = _quarantine_legacy_oauth(user_id, provider_id, legacy)
        if _auth_json_has_oauth_material(legacy) and not quarantined:
            _device_oauth_session_patch(session_id, {"status": "error", "finalized": False})
            return {
                "ok": False,
                "provider": provider_id,
                "session_id": session_id,
                "status": "error",
                "error": "oauth_quarantine_failed",
                "message": "OAuth material was not quarantined; runtime authority was left untouched.",
            }
    _finalize_hermes_device_oauth(user_id, provider_id, spec)
    _device_oauth_session_patch(session_id, {"status": "error", "finalized": True})
    return {
        "ok": False,
        "provider": provider_id,
        "session_id": session_id,
        "status": "error",
        "error": "oauth_broker_unsupported",
        "message": "OAuth completed upstream, but this Workframe install has no server-side refresh broker; no runtime token was published.",
    }


def _device_oauth_session_get(session_id: str) -> dict[str, Any] | None:
    with _oauth_device_lock:
        row = _oauth_device_sessions.get(str(session_id or "").strip())
        return dict(row) if isinstance(row, dict) else None


def _device_oauth_session_patch(session_id: str, patch: dict[str, Any]) -> None:
    with _oauth_device_lock:
        row = _oauth_device_sessions.get(session_id)
        if isinstance(row, dict):
            row.update(patch)


def _reusable_device_oauth_session(user_id: str, provider_id: str) -> tuple[str, dict[str, Any]] | None:
    """Reuse one live device flow instead of rate-limiting the upstream provider."""
    now = time.time()
    with _oauth_device_lock:
        candidates = [
            (session_id, dict(row))
            for session_id, row in _oauth_device_sessions.items()
            if isinstance(row, dict)
            and row.get("user_id") == user_id
            and row.get("provider_id") == provider_id
            and row.get("status") == "pending"
            and now - float(row.get("started_at") or 0.0) < 16 * 60
        ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: float(item[1].get("started_at") or 0.0))


def _spawn_hermes_device_oauth(user_id: str, hermes_auth_id: str, log_container: str) -> tuple[int, str]:
    """Start long-running `hermes auth add` detached in gateway (survives exec return)."""
    home = _srv()._hermes_user_home_container(user_id)
    _srv()._user_hermes_home(user_id).mkdir(parents=True, exist_ok=True)
    if _srv().SECURE_MODE and _srv()._supervisor_ready():
        status, data = _srv()._supervisor_request(
            "POST",
            "/v1/hermes.device_oauth_start",
            {"home": home, "hermes_auth_id": hermes_auth_id, "log_path": log_container},
            timeout=30.0,
        )
        if status >= 300:
            err = data.get("error") if isinstance(data, dict) else str(data)
            raise ValueError(err or "device_oauth_start_failed")
        if not isinstance(data, dict):
            raise ValueError("device_oauth_start_invalid")
        exit_code = data.get("exit_code")
        try:
            code = int(exit_code if exit_code is not None else 1)
        except (TypeError, ValueError):
            code = 1
        return code, str(data.get("output") or "")
    auth_cmd = " ".join(shlex.quote(part) for part in ["auth", "add", hermes_auth_id])
    shell = (
        f"mkdir -p {shlex.quote(home)}; "
        f"chown -R hermes:hermes {shlex.quote(home)}; "
        f"su -s /bin/sh hermes -c "
        f"'export HERMES_HOME={shlex.quote(home)} HOME={shlex.quote(home)}; "
        f"cd {shlex.quote(home)}; "
        f"/opt/hermes/bin/hermes {auth_cmd} >> {shlex.quote(log_container)} 2>&1'"
    )
    return _srv()._gateway_container_exec_detached(["sh", "-lc", shell])


def _start_device_oauth(
    user_id: str,
    provider_id: str,
    spec: dict[str, Any],
    workspace_id: str = "",
) -> dict[str, Any]:
    hermes_auth_id = _hermes_auth_id_for_spec(spec)
    if _hermes_oauth_tokens_present(user_id, hermes_auth_id):
        session_id = secrets.token_urlsafe(16)
        with _oauth_device_lock:
            _oauth_device_sessions[session_id] = {
                "user_id": user_id,
                "provider_id": provider_id,
                "hermes_auth_id": hermes_auth_id,
                "log_path": "",
                "status": "pending",
                "verification_uri": None,
                "user_code": None,
                "finalized": False,
                "started_at": time.time(),
                "workspace_id": workspace_id,
            }
        return _adopt_hermes_device_oauth(user_id, provider_id, spec, session_id, workspace_id)
    if _user_provider_connected(user_id, spec):
        return {
            "ok": True,
            "provider": provider_id,
            "hermes_auth_id": hermes_auth_id,
            "flow": "device_code",
            "status": "connected",
            "connected": True,
        }
    reusable = _reusable_device_oauth_session(user_id, provider_id)
    if reusable:
        reusable_id, _ = reusable
        current = device_oauth_status(user_id, provider_id, reusable_id)
        if current.get("status") != "error":
            return {
                "ok": True,
                "provider": provider_id,
                "hermes_auth_id": hermes_auth_id,
                "flow": "device_code",
                "session_id": reusable_id,
                "status": current.get("status") or "pending",
                "verification_uri": current.get("verification_uri"),
                "user_code": current.get("user_code"),
                "message": current.get("message"),
                "reused": True,
            }
    session_id = secrets.token_urlsafe(16)
    log_name = f".oauth-{session_id}.log"
    home = _srv()._hermes_user_home_container(user_id)
    log_container = f"{home}/{log_name}"
    log_host = _srv()._user_hermes_home(user_id) / log_name
    try:
        rc, out = _spawn_hermes_device_oauth(user_id, hermes_auth_id, log_container)
    except (RuntimeError, ValueError) as exc:
        return {"ok": False, "provider": provider_id, "error": str(exc)}
    if rc != 0:
        output = (out or "").strip()
        return {
            "ok": False,
            "provider": provider_id,
            "error": "oauth_start_failed",
            "output": output,
            "message": _device_oauth_error_from_log(output) or output[-500:] or "Could not start OAuth",
        }
    with _oauth_device_lock:
        _oauth_device_sessions[session_id] = {
            "user_id": user_id,
            "provider_id": provider_id,
            "hermes_auth_id": hermes_auth_id,
            "log_path": str(log_host),
            "status": "pending",
            "verification_uri": None,
            "user_code": None,
            "finalized": False,
            "started_at": time.time(),
            "workspace_id": workspace_id,
        }
    status = device_oauth_status(user_id, provider_id, session_id)
    return {
        "ok": True,
        "provider": provider_id,
        "hermes_auth_id": hermes_auth_id,
        "flow": "device_code",
        "session_id": session_id,
        "status": status.get("status") or "pending",
        "verification_uri": status.get("verification_uri"),
        "user_code": status.get("user_code"),
        "message": status.get("message"),
    }


def device_oauth_status(user_id: str, provider_id: str, session_id: str) -> dict[str, Any]:
    sess = _device_oauth_session_get(session_id)
    if not sess or sess.get("user_id") != user_id or sess.get("provider_id") != provider_id:
        return {"ok": False, "error": "session_not_found"}
    spec = _srv()._catalog_provider(provider_id) or {}
    hermes_auth_id = str(sess.get("hermes_auth_id") or _hermes_auth_id_for_spec(spec))
    log_path = Path(str(sess.get("log_path") or ""))
    log_text = ""
    if log_path.is_file():
        try:
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            log_text = ""
    if not log_text.strip() and log_path.name:
        log_text = _read_gateway_data_file(f"profiles/{_srv()._user_hermes_dir_slug(user_id)}/{log_path.name}")
    parsed = _parse_device_oauth_log(log_text)
    patch: dict[str, Any] = {}
    if parsed.get("verification_uri"):
        patch["verification_uri"] = parsed["verification_uri"]
    if parsed.get("user_code"):
        patch["user_code"] = parsed["user_code"]
    if patch:
        _device_oauth_session_patch(session_id, patch)
        sess.update(patch)
    log_error = _device_oauth_error_from_log(log_text)
    if log_error:
        _device_oauth_session_patch(session_id, {"status": "error"})
        return {
            "ok": False,
            "provider": provider_id,
            "session_id": session_id,
            "status": "error",
            "error": "oauth_failed",
            "message": log_error,
            "verification_uri": sess.get("verification_uri"),
            "user_code": sess.get("user_code"),
        }
    if sess.get("status") == "connected" and sess.get("finalized"):
        return _connected_device_oauth_payload(
            user_id,
            provider_id,
            session_id,
            verification_uri=sess.get("verification_uri"),
            user_code=sess.get("user_code"),
        )
    workspace_id = str(sess.get("workspace_id") or "")
    if _hermes_oauth_tokens_present(user_id, hermes_auth_id):
        return _adopt_hermes_device_oauth(user_id, provider_id, spec, session_id, workspace_id)
    lowered = log_text.lower()
    if any(token in lowered for token in ("login successful", "auth added", "credentials saved", "successfully authenticated", "logged in")):
        if _hermes_oauth_tokens_present(user_id, hermes_auth_id):
            return _adopt_hermes_device_oauth(user_id, provider_id, spec, session_id, workspace_id)
        if _user_provider_connected(user_id, spec):
            _device_oauth_session_patch(session_id, {"status": "connected", "finalized": True})
            return _connected_device_oauth_payload(
                user_id,
                provider_id,
                session_id,
                verification_uri=sess.get("verification_uri"),
                user_code=sess.get("user_code"),
            )
        return _oauth_broker_unsupported(user_id, provider_id, spec, session_id)
    if any(token in lowered for token in ("autherror", "login timed out", "login cancelled", "failed")):
        _device_oauth_session_patch(session_id, {"status": "error"})
        return {
            "ok": False,
            "provider": provider_id,
            "session_id": session_id,
            "status": "error",
            "error": "oauth_failed",
            "message": _device_oauth_error_from_log(log_text) or _strip_ansi(log_text).strip()[-500:] or "OAuth failed",
            "verification_uri": sess.get("verification_uri"),
            "user_code": sess.get("user_code"),
        }
    started = float(sess.get("started_at") or 0.0)
    if started and time.time() - started > 16 * 60:
        _device_oauth_session_patch(session_id, {"status": "error"})
        return {
            "ok": False,
            "provider": provider_id,
            "session_id": session_id,
            "status": "error",
            "error": "oauth_timeout",
            "verification_uri": sess.get("verification_uri"),
            "user_code": sess.get("user_code"),
        }
    return {
        "ok": True,
        "provider": provider_id,
        "session_id": session_id,
        "status": "pending",
        "verification_uri": sess.get("verification_uri"),
        "user_code": sess.get("user_code"),
    }


def start_user_oauth(user_id: str, provider_id: str, workspace_id: str = "") -> dict[str, Any]:
    if str(provider_id).lower() == "discord":
        return _srv()._start_discord_oauth(user_id, workspace_id)
    spec = _srv()._catalog_provider(provider_id)
    if not spec or str(spec.get("connect_mode")) != "oauth":
        return {"ok": False, "error": "not_oauth_provider"}
    oauth_provider = str(spec.get("oauth_provider") or spec["id"]).lower()
    if oauth_provider == "github":
        return {**_srv()._start_github_oauth(user_id, workspace_id, spec), "flow": "redirect"}
    if oauth_provider == "stripe":
        return {**_srv()._start_stripe_oauth(user_id, workspace_id, spec), "flow": "redirect"}
    if str(provider_id).lower() in _DEVICE_OAUTH_PROVIDER_IDS:
        return _start_device_oauth(user_id, provider_id, spec, workspace_id)
    hermes_auth_id = _hermes_auth_id_for_spec(spec)
    rc, out = _srv()._hermes_user_exec(user_id, ["auth", "add", hermes_auth_id])
    redirect_url = None
    for token in re.findall(r"https?://[^\s\])>\"']+", out or ""):
        redirect_url = token.rstrip(".,;)")
        break
    return {
        "ok": rc == 0,
        "provider": provider_id,
        "hermes_auth_id": hermes_auth_id,
        "output": (out or "").strip(),
        "redirect_url": redirect_url,
        "flow": "redirect" if redirect_url else "device_code",
        "error": None if rc == 0 else "oauth_start_failed",
    }
