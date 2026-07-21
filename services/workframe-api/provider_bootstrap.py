"""WF-032 extract: provider_bootstrap."""
from __future__ import annotations

import json
import os
import queue
import re
import secrets
import shlex
import shutil
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from http.server import BaseHTTPRequestHandler

import user_prefs


def _srv():
    import server as srv

    return srv


def _load_profile_auth_json(profile: str) -> dict[str, Any]:
    path = _srv()._profile_dir(profile) / "auth.json"
    fallback: dict[str, Any] = {"version": 1, "providers": {}, "credential_pool": {}}
    if not path.is_file():
        return dict(fallback)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(fallback)
    return raw if isinstance(raw, dict) else dict(fallback)


def _provider_pool_entry(provider: str, env_var: str, *, base_url: str = "") -> dict[str, Any]:
    base_urls = {
        "openrouter": "https://openrouter.ai/api/v1",
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com",
    }
    resolved_base = str(base_url or "").strip() or base_urls.get(provider.lower(), "")
    return {
        "id": secrets.token_hex(3),
        "label": env_var,
        "auth_type": "api_key",
        "priority": 0,
        "source": f"env:{env_var}",
        "last_status": "ok",
        "base_url": resolved_base,
        "request_count": 0,
    }


def _runtime_provider_pool_entry(provider: str, env_var: str) -> dict[str, Any]:
    """Credential pool row for u-* profiles — lease token lives in OPENAI_API_KEY."""
    lease_env = "OPENAI_API_KEY"
    return _provider_pool_entry(provider, lease_env, base_url=_srv()._llm_proxy_base_url(provider))


def _provider_pool_has_entries(auth: dict[str, Any], provider: str) -> bool:
    pool = auth.get("credential_pool")
    if not isinstance(pool, dict):
        return False
    provider_key = str(provider or "").strip().lower()
    for key in _srv()._hermes_oauth_auth_keys(provider_key) | {provider_key}:
        entries = pool.get(key)
        if isinstance(entries, list) and len(entries) > 0:
            return True
    spec = _srv()._catalog_provider_for_llm(provider_key)
    if spec:
        auth_id = str(spec.get("hermes_auth_id") or "").strip().lower()
        if auth_id:
            entries = pool.get(auth_id)
            if isinstance(entries, list) and len(entries) > 0:
                return True
    return False


def _connected_provider_names(user_id: str = "", workspace_id: str = "") -> set[str]:
    names: set[str] = set()
    user = str(user_id or "").strip()
    workspace = str(workspace_id or "").strip()
    if user:
        names.update(_srv()._user_provider_bindings(user).keys())
        names.update(
            str(spec["id"]).lower()
            for spec in _srv().PROVIDER_CONNECT_CATALOG
            if str(spec.get("env_var") or "") in _srv()._user_auth_env_keys(user)
        )
    if workspace:
        for provider in ("openrouter", "openai", "anthropic", "google"):
            if _srv()._resolve_credential("", workspace, provider):
                names.add(provider)
    if not user:
        primary = _srv()._primary_profile()
        if primary:
            primary_pool = _load_profile_auth_json(primary).get("credential_pool")
            if isinstance(primary_pool, dict):
                for pname, entries in primary_pool.items():
                    if isinstance(entries, list) and entries:
                        names.add(str(pname).lower())
        if not names:
            names.add("openrouter")
    return names


def _user_llm_providers_for_picker(user_id: str) -> set[str]:
    user = str(user_id or "").strip()
    if not user:
        return set()
    now = time.monotonic()
    cached = _srv()._user_llm_picker_cache.get(user)
    if cached and now - cached[1] < _srv()._USER_LLM_PICKER_TTL_SEC:
        return set(cached[0])
    connected = frozenset(
        str(spec["id"]).lower()
        for spec in _srv().PROVIDER_CONNECT_CATALOG
        if str(spec.get("category") or "") == "llm" and _srv()._user_provider_connected(user, spec)
    )
    _srv()._user_llm_picker_cache[user] = (connected, now)
    return set(connected)


def invalidate_user_llm_picker_cache(user_id: str = "") -> None:
    """Forget cached provider availability after a credential mutation."""
    user = str(user_id or "").strip()
    if user:
        _srv()._user_llm_picker_cache.pop(user, None)
    else:
        _srv()._user_llm_picker_cache.clear()


def _user_has_llm_provider(user_id: str) -> bool:
    return bool(_srv()._user_llm_providers_for_picker(user_id))


def _user_llm_has_provider(user_id: str, workspace_id: str = "") -> bool:
    if _user_has_llm_provider(user_id):
        return True
    ws = str(workspace_id or "").strip()
    return bool(ws and _workspace_has_llm_provider(ws))


def _workspace_has_llm_provider(workspace_id: str) -> bool:
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return False
    for spec in _srv().PROVIDER_CONNECT_CATALOG:
        if str(spec.get("category") or "") != "llm":
            continue
        provider_id = str(spec["id"])
        resolved = _srv()._resolve_credential("", workspace_id, provider_id)
        if not resolved:
            continue
        env_var = str(spec.get("env_var") or "")
        if env_var and _srv()._stack_profile_env().get(env_var):
            return True
    return False


def _user_can_use_llm(user_id: str, workspace_id: str = "", provider: str = "openrouter") -> bool:
    user = str(user_id or "").strip()
    if not user:
        return False
    spec = _srv()._catalog_provider_for_llm(provider)
    if spec and str(spec.get("connect_mode") or "") == "oauth":
        return _srv()._hermes_oauth_tokens_present(user, _srv()._hermes_auth_id_for_spec(spec))
    try:
        resolved = _srv()._require_user_provider(user, workspace_id, provider)
        return bool(_srv()._credential_secret(resolved, user))
    except ValueError:
        return False


def _overlay_chat_llm_env(
    hermes_prof: str,
    user_id: str,
    workspace_id: str,
    provider: str,
) -> bool:
    """Overlay turn credentials; True when this turn can bill the acting user's key."""
    user = str(user_id or "").strip()
    if not user:
        return False
    prov = _srv()._llm_billing_provider(hermes_prof, provider, user_id=user, workspace_id=workspace_id)
    if not _srv()._profile_llm_proxy_matches_billing(hermes_prof, prov):
        _srv()._ensure_profile_llm_proxy(hermes_prof, prov)
    slug = _srv().safe_profile_slug(hermes_prof)
    turn_run = str(uuid.uuid4())
    ready = _srv()._try_overlay_turn_provider_env(hermes_prof, user, workspace_id, prov, turn_run)
    if ready:
        _srv()._overlay_turn_user_env(hermes_prof, user, workspace_id, turn_run)
        return True
    if _srv()._is_runtime_profile_slug(slug):
        return False
    return _srv()._user_can_use_llm(user, workspace_id, prov)



def _reconcile_profile_llm_for_user(
    profile: str,
    user_id: str,
    workspace_id: str,
    *,
    prefer_provider: str = "",
) -> bool:
    """Repair routing for the agent-owned model without changing that model.

    Credentials authorize execution; they never silently select a different
    provider and create DM/room model drift.
    """
    user = str(user_id or "").strip()
    if not user:
        return False
    prof = _srv().resolve_hermes_profile(profile)
    block = _srv()._read_model_block(prof)
    current_model = str(block.get("default") or "").strip()
    cfg = str(block.get("provider") or "").strip().lower()
    configured_billing = (
        _srv()._billing_provider_from_block(
            str(block.get("base_url") or ""),
            cfg,
            cfg,
        )
        if (cfg or block.get("base_url"))
        else ""
    )
    connected = _srv()._user_llm_providers_for_picker(user)
    prefer = str(prefer_provider or "").strip().lower()
    if configured_billing and current_model:
        billing = configured_billing
    elif prefer and _srv()._user_can_use_llm(user, workspace_id, prefer):
        billing = prefer
    else:
        connected_sorted = sorted(connected)
        if not connected_sorted:
            return False
        billing = connected_sorted[0]

    if not current_model:
        current_model = str(
            (_srv().PROVIDER_MVP_MODELS.get(billing) or {}).get("primary") or ""
        ).strip()
        if not current_model:
            return False

    if _srv()._oauth_llm_provider_spec(billing):
        if _srv()._profile_routing_matches_billing(prof, billing, block=block):
            auth_changed = bool(
                _srv()._user_can_use_llm(user, workspace_id, billing)
                and _srv()._sync_oauth_llm_to_profile(prof, user, billing)
            )
            if auth_changed:
                _srv()._reload_runtime_profile_gateway(prof, wait_healthy=True)
            return auth_changed
        changed = _srv()._apply_model_for_billing_provider(
            prof,
            billing,
            current_model,
            user_id=user if _srv()._user_can_use_llm(user, workspace_id, billing) else "",
        )
        if changed:
            _srv()._reload_runtime_profile_gateway(prof, wait_healthy=True)
        return changed

    if _srv()._profile_routing_matches_billing(prof, billing, block=block):
        if not _srv()._profile_llm_proxy_ready(prof, billing):
            before = _srv()._parse_model_block_from_disk(prof)
            _srv()._ensure_profile_llm_proxy(prof, billing)
            changed = before != _srv()._parse_model_block_from_disk(prof)
            if changed:
                _srv()._reload_runtime_profile_gateway(prof, wait_healthy=True)
            return changed
        return False

    # API-key providers are vault-backed. Repair transport to the internal
    # proxy while preserving the exact agent-selected model id.
    changed = _srv()._apply_model_for_billing_provider(
        prof,
        billing,
        current_model,
        user_id=user,
    )
    if changed:
        _srv()._ensure_profile_llm_proxy(prof, billing)
        _srv()._reload_runtime_profile_gateway(prof, wait_healthy=True)
    return changed


def _ensure_profile_auth_pool(profile: str, user_id: str = "", workspace_id: str = "") -> bool:
    """Sync auth.json credential pool — does not mutate model yaml (safe on GET /models)."""
    prof = _srv().resolve_hermes_profile(profile)
    if prof == _srv()._primary_profile():
        return False
    if _srv()._is_runtime_profile_slug(prof):
        _srv()._strip_profile_llm_env(prof)
        _srv()._strip_profile_action_env(prof)
    else:
        _srv()._strip_profile_llm_env(prof)
        _srv()._strip_profile_action_env(prof)
        _srv()._sync_profile_provider_env(prof, user_id, workspace_id)

    llm_provider = _srv()._llm_billing_provider(prof, user_id=user_id, workspace_id=workspace_id)
    auth_path = _srv()._profile_dir(prof) / "auth.json"
    auth = _load_profile_auth_json(prof)
    if _provider_pool_has_entries(auth, llm_provider):
        return False

    user = str(user_id or "").strip()
    llm_spec = _srv()._catalog_provider_for_llm(llm_provider)
    if (
        llm_spec
        and str(llm_spec.get("connect_mode") or "") == "oauth"
        and user
        and _srv()._sync_oauth_llm_to_profile(prof, user, llm_provider)
    ):
        return True

    if _srv()._is_runtime_profile_slug(prof):
        if not user or not _srv()._user_can_use_llm(user, workspace_id, llm_provider):
            return False
        env_var = _srv()._provider_env_var(llm_provider)
        template = _runtime_provider_pool_entry(llm_provider, env_var)
    else:
        resolved = _srv()._resolve_credential(
            user,
            str(workspace_id or "").strip(),
            llm_provider,
            user_only=_srv()._provider_user_only(llm_provider),
        )
        if not resolved:
            return False

        ref = str(resolved.get("credential_ref") or "")
        env_var = str(resolved.get("env_var") or "") or (ref[4:] if ref.startswith("env:") else _srv()._provider_env_var(llm_provider))
        template = _provider_pool_entry(llm_provider, env_var)

    pool = auth.setdefault("credential_pool", {})
    if not isinstance(pool, dict):
        pool = {}
        auth["credential_pool"] = pool
    pool[llm_provider] = [template]
    auth["version"] = 1
    auth["providers"] = auth.get("providers") if isinstance(auth.get("providers"), dict) else {}
    auth["updated_at"] = _srv()._utc_now()
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(json.dumps(auth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _srv()._publish_profile_gateway_secrets(prof)
    return True


def _bootstrap_profile_providers(profile: str, user_id: str = "", workspace_id: str = "") -> bool:
    """Seed profile auth + MVP model config from user, workspace, or primary stack."""
    prof = _srv().resolve_hermes_profile(profile)
    if prof == _srv()._primary_profile():
        return False

    changed = _srv()._ensure_profile_auth_pool(prof, user_id, workspace_id)

    provider, model_name = _srv()._read_model_from_config(prof)
    llm_provider = _srv()._llm_billing_provider(prof, provider or "")
    # ChatGPT-account Codex rejects the historical gpt-5.4-medium default.
    # Migrate generated profiles during ordinary bootstrap so existing installs
    # converge without requiring users to delete their agent/session data.
    if llm_provider == "codex" and str(model_name or "").strip() == "gpt-5.4-medium":
        ok_model, _ = _srv()._set_profile_model(prof, "gpt-5.4-mini")
        changed = ok_model or changed
        model_name = "gpt-5.4-mini"

    if not str(model_name or "").strip():
        changed = _srv()._apply_mvp_model_for_provider(prof, llm_provider) or changed
        if _srv()._is_runtime_profile_slug(prof):
            _srv()._ensure_profile_llm_proxy(prof, llm_provider)
    elif not str(_srv()._read_model_from_config(prof)[0] or "").strip():
        ok_provider, _ = _srv()._set_profile_model_provider(prof, llm_provider)
        changed = ok_provider or changed
        if _srv()._is_runtime_profile_slug(prof):
            _srv()._ensure_profile_llm_proxy(prof, llm_provider)

    if _srv()._is_runtime_profile_slug(prof):
        _srv()._prepare_runtime_profile_credentials(prof, user_id, workspace_id)

    return changed
