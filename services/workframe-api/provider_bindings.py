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


def _srv():
    import server as srv

    return srv


_load_profile_auth_json = provider_bootstrap._load_profile_auth_json

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


def _extract_oauth_block_from_auth(loaded: dict[str, Any], hermes_auth_id: str) -> dict[str, Any] | None:
    keys = _hermes_oauth_auth_keys(hermes_auth_id)
    providers = loaded.get("providers")
    if isinstance(providers, dict):
        for key, entry in providers.items():
            if str(key).lower() in keys and isinstance(entry, dict):
                tokens = entry.get("tokens")
                if isinstance(tokens, dict) and any(
                    str(tokens.get(field) or "").strip()
                    for field in ("access_token", "refresh_token", "api_key", "id_token")
                ):
                    return entry
                if entry:
                    return entry
    creds = loaded.get("credentials")
    if isinstance(creds, list):
        for row in creds:
            if not isinstance(row, dict):
                continue
            pid = str(row.get("provider") or row.get("id") or "").lower()
            if pid in keys:
                return row
    return None


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
                pool[hermes_auth_id] = entries
                changed = True
    return changed


def _sync_oauth_llm_to_profile(profile: str, user_id: str, provider: str) -> bool:
    spec = _oauth_llm_provider_spec(provider)
    if not spec:
        return False
    hermes_auth_id = _hermes_auth_id_for_spec(spec)
    if not _hermes_oauth_tokens_present(user_id, hermes_auth_id):
        return False
    prof = _srv().resolve_hermes_profile(profile)
    auth = _load_profile_auth_json(prof)
    user_auth = _load_user_hermes_auth(user_id)
    if not isinstance(user_auth, dict):
        return False
    auth_path = _srv()._profile_dir(prof) / "auth.json"
    before = json.dumps(auth, sort_keys=True, separators=(",", ":"))
    if not _merge_oauth_auth_into_profile(auth, user_auth, hermes_auth_id):
        return False
    after = json.dumps(auth, sort_keys=True, separators=(",", ":"))
    if after == before:
        return False
    auth["version"] = 1
    auth["updated_at"] = _srv()._utc_now()
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(json.dumps(auth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _srv()._publish_profile_gateway_secrets(prof)
    return True


def _hermes_oauth_tokens_present(user_id: str, hermes_auth_id: str) -> bool:
    """True when Hermes auth.json has live OAuth tokens for a provider."""
    hermes_auth_id = str(hermes_auth_id or "").strip()
    if not hermes_auth_id:
        return False
    loaded = _load_user_hermes_auth(user_id)
    if not isinstance(loaded, dict):
        return False
    if _extract_oauth_block_from_auth(loaded, hermes_auth_id):
        return True
    keys = _hermes_oauth_auth_keys(hermes_auth_id)
    pool = loaded.get("credential_pool")
    if isinstance(pool, dict):
        for key, entries in pool.items():
            if str(key).lower() in keys and isinstance(entries, list) and entries:
                return True
    return False


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
    full = f"/opt/data/{rel_path}"
    try:
        code, out = _srv()._gateway_container_exec(["cat", full])
        return out if code == 0 else ""
    except Exception:
        return ""


def _user_provider_connected(user_id: str, spec: dict[str, Any]) -> bool:
    """Connected = this user's credential resolves with a live secret (no stack/install bleed)."""
    if str(spec.get("connect_mode") or "") == "oauth":
        if _hermes_oauth_tokens_present(user_id, _hermes_auth_id_for_spec(spec)):
            return True
    provider_id = str(spec["id"])
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
        now = _srv()._utc_now()
        conn.execute(
            "UPDATE credential_bindings SET is_active = 0, deleted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, credential_id),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"db_error: {exc}"}
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
            loaded = {}
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
    if not _hermes_oauth_tokens_present(user_id, hermes_auth_id):
        return
    user_auth = _load_user_hermes_auth(user_id)
    if not isinstance(user_auth, dict):
        return
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
        user_auth = _load_user_hermes_auth(user_id)
        if not isinstance(user_auth, dict):
            continue
        if not _merge_oauth_auth_into_profile(auth, user_auth, hermes_auth_id):
            continue
        auth["version"] = 1
        auth["updated_at"] = _srv()._utc_now()
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        auth_path.write_text(json.dumps(auth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _srv()._publish_profile_gateway_secrets(prof_dir.name)


def _finalize_hermes_device_oauth(user_id: str, provider_id: str, spec: dict[str, Any]) -> None:
    hermes_auth_id = _hermes_auth_id_for_spec(spec)
    _sync_user_oauth_provider_to_runtime_profiles(user_id, hermes_auth_id)
    # The picker caches connected providers for one minute. OAuth material is
    # stored outside credential_bindings, so the ordinary secret-save
    # invalidation path never runs; clear it before selecting/bootstraping the
    # new provider or the completed Codex connection remains invisible.
    _srv()._invalidate_user_llm_picker_cache(user_id)
    _srv()._bootstrap_model_after_llm_connect(user_id, "", provider_id)


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


def _start_device_oauth(user_id: str, provider_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    hermes_auth_id = _hermes_auth_id_for_spec(spec)
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
    if _hermes_oauth_tokens_present(user_id, hermes_auth_id):
        if not sess.get("finalized"):
            _finalize_hermes_device_oauth(user_id, provider_id, spec)
            _device_oauth_session_patch(session_id, {"status": "connected", "finalized": True})
        return {
            "ok": True,
            "provider": provider_id,
            "session_id": session_id,
            "status": "connected",
            "verification_uri": sess.get("verification_uri"),
            "user_code": sess.get("user_code"),
        }
    lowered = log_text.lower()
    if any(token in lowered for token in ("login successful", "auth added", "credentials saved", "successfully authenticated", "logged in")):
        if _hermes_oauth_tokens_present(user_id, hermes_auth_id):
            if not sess.get("finalized"):
                _finalize_hermes_device_oauth(user_id, provider_id, spec)
                _device_oauth_session_patch(session_id, {"status": "connected", "finalized": True})
            return {
                "ok": True,
                "provider": provider_id,
                "session_id": session_id,
                "status": "connected",
                "verification_uri": sess.get("verification_uri"),
                "user_code": sess.get("user_code"),
            }
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
        return _start_device_oauth(user_id, provider_id, spec)
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
