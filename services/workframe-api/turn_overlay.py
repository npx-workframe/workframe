"""WF-032 extract: per-turn credential leases and LLM proxy profile overlays."""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

import credential_vault
import internal_proxy_auth
import profile_config_yaml
import provider_catalog
import turn_credentials


def _srv():
    import server as srv

    return srv


PROXY_HEADER_TEMPLATE = "${WORKFRAME_PROXY_TOKEN}"

def _llm_proxy_base_url(provider: str) -> str:
    return f"{_srv().WORKFRAME_LLM_PROXY_INTERNAL}/internal/llm/{str(provider or 'openrouter').strip().lower()}/v1"


def _upsert_model_default_header(
    lines: list[str],
    header_key: str,
    header_val: str,
) -> list[str]:
    """Ensure model.default_headers contains header_key: header_val (single block)."""
    text = "".join(lines)
    if f"{header_key}: {header_val}" in text or f"{header_key}: '{header_val}'" in text:
        return lines
    out: list[str] = []
    in_model = False
    in_headers = False
    wrote = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("model:"):
            in_model = True
            in_headers = False
            out.append(line)
            continue
        if in_model and stripped.startswith("default_headers:"):
            in_headers = True
            out.append(line)
            continue
        if in_model and in_headers and stripped.startswith(f"{header_key}:"):
            indent = line[: len(line) - len(stripped)]
            out.append(f"{indent}{header_key}: {header_val}\n")
            wrote = True
            continue
        if in_model and in_headers and not wrote:
            # ponytail: sibling model keys + top-level keys end the headers block â€” append before them
            ends_headers = bool(
                stripped and not line.startswith(("    ", "\t")) and not stripped.startswith("#")
            )
            if ends_headers:
                out.append(f"    {header_key}: {header_val}\n")
                wrote = True
                in_headers = False
        if in_model and stripped and not line.startswith((" ", "\t", "#")):
            if not wrote and not in_headers:
                out.append("  default_headers:\n")
                out.append(f"    {header_key}: {header_val}\n")
                wrote = True
            in_model = False
            in_headers = False
        out.append(line)
    if not wrote:
        rebuilt: list[str] = []
        inserted = False
        for line in out:
            rebuilt.append(line)
            if not inserted and line.lstrip().startswith("model:"):
                rebuilt.append("  default_headers:\n")
                rebuilt.append(f"    {header_key}: {header_val}\n")
                inserted = True
        if not inserted:
            rebuilt.insert(
                0,
                f"model:\n  default_headers:\n    {header_key}: {header_val}\n",
            )
        out = rebuilt
    return out


def _ensure_profile_proxy_headers(profile: str) -> None:
    """Hermes default_headers: proxy token + profile slug for lease binding at /internal/*."""
    prof = _srv().safe_profile_slug(profile)
    _srv()._normalize_profile_config_yaml(prof)
    try:
        config_path = _srv()._ensure_gateway_config_file(prof)
    except ValueError:
        return
    header_specs: list[tuple[str, str]] = [(internal_proxy_auth.PROFILE_HEADER, prof)]
    if internal_proxy_auth.proxy_token_configured():
        header_specs.append((internal_proxy_auth.PROXY_TOKEN_HEADER, PROXY_HEADER_TEMPLATE))
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError:
        return
    lines = raw.splitlines(keepends=True)
    for header_key, header_val in header_specs:
        lines = _upsert_model_default_header(lines, header_key, header_val)
    try:
        config_path.write_text("".join(lines), encoding="utf-8")
    except OSError:
        return


def _set_profile_model_base_url(profile: str, base_url: str) -> tuple[bool, str]:
    _srv()._normalize_profile_config_yaml(profile)
    try:
        config_path = _srv()._ensure_gateway_config_file(profile)
    except ValueError as exc:
        return False, str(exc)
    base_url = str(base_url or "").strip()
    if not base_url:
        return False, "base_url required"
    try:
        profile_config_yaml.update_model_surface(config_path, base_url=base_url)
    except OSError as exc:
        return False, f"write failed: {exc}"
    return True, ""


def _proxy_fallback_chain(profile: str, billing_provider: str) -> None:
    """Runtime fallbacks use provider=custom so Hermes keeps the proxy + lease."""
    if not _srv()._is_runtime_profile_slug(profile):
        return
    block = _srv()._read_model_block(profile)
    chain = block.get("fallback_chain") or []
    billing = str(billing_provider or "openrouter").strip().lower()
    proxied: list[dict[str, str]] = []
    changed = False
    for entry in chain:
        prov = str(entry.get("provider", "")).strip().lower()
        model = str(entry.get("model", "")).strip()
        if not prov or not model:
            continue
        if prov == billing and prov != "custom":
            changed = True
            proxied.append({"provider": "custom", "model": model})
        else:
            proxied.append({"provider": prov, "model": model})
    if not proxied:
        changed = True
        proxied = [
            {"provider": "custom", "model": str(entry.get("model", "")).strip()}
            for entry in _srv().HERMES_DEFAULT_FALLBACK_CHAIN
            if str(entry.get("model", "")).strip()
        ]
    if changed:
        _srv()._write_fallback_chain(profile, proxied)


def _coalesce_profile_model_yaml(profile: str) -> None:
    """Merge duplicate top-level `model:` blocks left by incremental config writers."""
    config_path = _srv()._profile_gateway_config_path(profile)
    if not config_path or not config_path.is_file():
        return
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return
    model_headers = sum(
        1 for line in lines if line.lstrip().startswith("model:") and not line.startswith((" ", "\t"))
    )
    needs_coalesce = model_headers > 1
    if not needs_coalesce:
        in_model = False
        for line in lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if indent == 0 and stripped.startswith("model:"):
                in_model = True
                continue
            if indent == 0 and stripped:
                in_model = False
            if in_model and indent == 2 and stripped.startswith("- "):
                needs_coalesce = True
                break
    if not needs_coalesce:
        return
    block = _srv()._read_model_block(profile)
    default = str(block.get("default") or _srv().HERMES_DEFAULT_PRIMARY).strip()
    provider = str(block.get("provider") or "").strip()
    base_url = str(block.get("base_url") or "").strip()
    api_key = str(block.get("api_key") or "").strip()
    chain = block.get("fallback_chain") if isinstance(block.get("fallback_chain"), list) else []
    try:
        profile_config_yaml.update_model_surface(
            config_path,
            default=default,
            provider=provider or None,
            base_url=base_url or None,
            api_key=api_key or None,
            fallback_chain=chain,
            coalesce=True,
        )
    except OSError:
        return


def _profile_llm_proxy_ready(profile: str, provider: str) -> bool:
    prof = _srv().safe_profile_slug(profile)
    block = _srv()._read_model_block(prof)
    llm_provider = str(provider or "openrouter").strip().lower()
    if str(block.get("base_url") or "").strip() != _llm_proxy_base_url(llm_provider):
        return False
    if not _srv()._is_runtime_profile_slug(prof):
        return True
    if str(block.get("provider") or "").strip().lower() != "custom":
        return False
    for entry in block.get("fallback_chain") or []:
        prov = str(entry.get("provider", "")).strip().lower()
        model = str(entry.get("model", "")).strip()
        if model and prov == llm_provider and prov != "custom":
            return False
    return True


def _ensure_profile_llm_proxy(profile: str, provider: str) -> None:
    """Point Hermes at the internal LLM proxy (create/lease paths only â€” skip when ready)."""
    llm_provider = str(provider or "openrouter").strip().lower()
    prof = _srv().safe_profile_slug(profile)
    if _srv()._oauth_llm_provider_spec(llm_provider):
        _srv()._normalize_profile_config_yaml(prof)
        _srv()._apply_mvp_model_for_provider(prof, llm_provider)
        return
    _srv()._normalize_profile_config_yaml(prof)
    if _profile_llm_proxy_ready(prof, llm_provider):
        _ensure_profile_proxy_headers(prof)
        if _srv()._is_runtime_profile_slug(prof):
            _proxy_fallback_chain(prof, llm_provider)
        return
    _coalesce_profile_model_yaml(prof)
    _set_profile_model_base_url(prof, _llm_proxy_base_url(llm_provider))
    _ensure_profile_proxy_headers(prof)
    if _srv()._is_runtime_profile_slug(prof):
        _srv()._set_profile_model_provider(prof, "custom")
        _proxy_fallback_chain(prof, llm_provider)


def _set_profile_model_api_key(profile: str, api_key: str) -> tuple[bool, str]:
    _srv()._normalize_profile_config_yaml(profile)
    try:
        config_path = _srv()._ensure_gateway_config_file(profile)
    except ValueError as exc:
        return False, str(exc)
    value = str(api_key or "").strip()
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"read failed: {exc}"
    lines = raw.splitlines(keepends=True)
    out: list[str] = []
    in_model = False
    wrote = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("model:"):
            if not in_model:
                in_model = True
                out.append(line)
            continue
        if in_model and stripped and not line.startswith((" ", "\t", "#")):
            if not wrote:
                out.append(f"  api_key: {_srv()._quote_env_value(value)}\n" if value else "  api_key: ''\n")
                wrote = True
            in_model = False
        if in_model and stripped.startswith("api_key:"):
            out.append(
                f"  api_key: {_srv()._quote_env_value(value)}\n" if value else "  api_key: ''\n"
            )
            wrote = True
            continue
        out.append(line)
    if not wrote:
        rebuilt: list[str] = []
        inserted = False
        for line in out:
            rebuilt.append(line)
            if not inserted and line.lstrip().startswith("model:"):
                rebuilt.append(
                    f"  api_key: {_srv()._quote_env_value(value)}\n" if value else "  api_key: ''\n"
                )
                inserted = True
        if not inserted:
            rebuilt.insert(0, f"model:\n  api_key: {_srv()._quote_env_value(value)}\n" if value else "model:\n  api_key: ''\n")
        out = rebuilt
    try:
        config_path.write_text("".join(out), encoding="utf-8")
    except OSError as exc:
        return False, f"write failed: {exc}"
    return True, ""


def _clear_profile_model_api_key(profile: str) -> None:
    _set_profile_model_api_key(profile, "")


def _profile_lease_env_var(profile: str, provider: str) -> str:
    prov, _model = _srv()._read_model_from_config(profile)
    if str(prov or "").strip().lower() == "custom":
        return "OPENAI_API_KEY"
    return _srv()._provider_env_var(provider)


def _read_profile_lease_token(profile: str, env_var: str) -> str:
    return str(_srv()._read_env_map(_srv()._profile_dir(profile) / ".env").get(env_var) or "").strip()


def _lease_reusable_for_turn(
    token: str,
    *,
    user_id: str,
    workspace_id: str,
    provider: str,
    binding_id: str,
) -> bool:
    lease = turn_credentials.validate_lease(token)
    if not lease:
        return False
    if str(lease.get("payer_user_id") or "") != str(user_id or "").strip():
        return False
    if str(lease.get("workspace_id") or "") != str(workspace_id or "").strip():
        return False
    if str(lease.get("provider") or "").strip().lower() != str(provider or "").strip().lower():
        return False
    lease_binding = str(lease.get("credential_binding_id") or "").strip()
    want_binding = str(binding_id or "").strip()
    if want_binding and lease_binding and lease_binding != want_binding:
        return False
    return True


def _read_config_model_api_key(profile: str) -> str:
    return str(_srv()._read_model_block(profile).get("api_key") or "").strip()




def _sync_profile_model_api_key(profile: str, api_key: str, *, wait_healthy: bool = False) -> None:
    value = str(api_key or "").strip()
    if not value:
        _clear_profile_model_api_key(profile)
        if wait_healthy:
            _srv()._restart_runtime_profile_gateway(profile)
        else:
            _srv()._schedule_gateway_reload(profile)
        return
    if _read_config_model_api_key(profile) == value:
        return
    ok, err = _set_profile_model_api_key(profile, value)
    if not ok:
        raise ValueError(err or "profile model api_key write failed")
    if wait_healthy:
        _srv()._restart_runtime_profile_gateway(profile)
    else:
        _srv()._schedule_gateway_reload(profile)


def _schedule_profile_lease_yaml_reconcile(
    profile: str,
    user_id: str,
    workspace_id: str,
    provider: str,
) -> None:
    """Bind path — align config.yaml lease token without blocking the client."""
    user = str(user_id or "").strip()
    prov = str(provider or "openrouter").strip().lower()
    if not user:
        return

    def _run() -> None:
        try:
            prof = _srv().resolve_hermes_profile(profile)
            if not _srv()._is_runtime_profile_slug(prof):
                return
            env_var = _profile_lease_env_var(prof, prov)
            token = _read_profile_lease_token(prof, env_var)
            if not token or _read_config_model_api_key(prof) == token:
                return
            _sync_profile_model_api_key(prof, token)
        except Exception:  # noqa: BLE001
            return

    threading.Thread(
        target=_run,
        name=f"lease-yaml-{profile}",
        daemon=True,
    ).start()


def _apply_turn_credential_lease(
    profile: str,
    user_id: str,
    workspace_id: str,
    provider: str,
    run_id: str,
) -> str:
    """Issue per-run lease token into profile env; real secret stays in API vault."""
    provider = str(provider or "openrouter").strip().lower()
    prof = _srv().resolve_hermes_profile(profile)
    env_var = _profile_lease_env_var(prof, provider)
    config_lease = _read_config_model_api_key(prof)
    if config_lease and not turn_credentials.validate_lease(config_lease):
        _clear_profile_model_api_key(prof)
    existing_token = _read_profile_lease_token(prof, env_var)
    if existing_token and not turn_credentials.validate_lease(existing_token):
        _strip_profile_llm_env(prof, include_leases=True)
        _clear_profile_model_api_key(prof)
        existing_token = ""
    if existing_token:
        lease_meta = turn_credentials.validate_lease(existing_token)
        if lease_meta and _lease_reusable_for_turn(
            existing_token,
            user_id=user_id,
            workspace_id=workspace_id,
            provider=provider,
            binding_id=str(lease_meta.get("credential_binding_id") or ""),
        ):
            # ponytail: hot path — skip credential resolve + env rewrite when lease still valid
            if _srv()._is_runtime_profile_slug(prof) and existing_token:
                if _read_config_model_api_key(prof) != existing_token:
                    _sync_profile_model_api_key(prof, existing_token)
            return existing_token

    if _srv()._is_runtime_profile_slug(prof):
        resolved = _require_runtime_owner_provider(user_id, workspace_id, provider)
    else:
        resolved = _require_user_provider(user_id, workspace_id, provider)
    oauth_spec = _srv()._oauth_llm_provider_spec(provider)
    if oauth_spec and str(resolved.get("credential_type") or "") == "oauth":
        _srv()._sync_oauth_llm_to_profile(prof, user_id, provider)
        if not _srv()._profile_routing_matches_billing(prof, provider):
            current_model = str(_srv()._read_model_from_config(prof)[1] or "").strip()
            if not _srv()._resolve_billing_provider_for_model(current_model, {provider}):
                current_model = str(
                    (_srv().PROVIDER_MVP_MODELS.get(provider) or {}).get("primary") or current_model
                ).strip()
            _srv()._apply_model_for_billing_provider(prof, provider, current_model, user_id)
        return ""
    binding_id = str(
        resolved.get("credential_binding_id") or resolved.get("credential_id") or ""
    ).strip()
    vault_id = credential_vault.parse_vault_ref(str(resolved.get("credential_ref") or ""))
    if vault_id:
        binding_id = vault_id
    if not binding_id and _srv()._credential_secret(resolved, user_id):
        binding_id = str(uuid.uuid4())
        credential_vault.store_secret(
            binding_id,
            _srv()._credential_secret(resolved, user_id),
            env_var=str(resolved.get("env_var") or "") or _srv()._provider_env_var(provider),
            provider=provider,
            scope=str(resolved.get("scope") or "user"),
            user_id=user_id,
            workspace_id=workspace_id,
        )
    if _lease_reusable_for_turn(
        existing_token,
        user_id=user_id,
        workspace_id=workspace_id,
        provider=provider,
        binding_id=binding_id,
    ):
        if _srv()._is_runtime_profile_slug(prof) and existing_token:
            if _read_config_model_api_key(prof) != existing_token:
                _sync_profile_model_api_key(prof, existing_token)
        return existing_token

    token = turn_credentials.issue_lease(
        run_id,
        user_id,
        workspace_id,
        provider,
        prof,
        binding_id or None,
    )
    if token != existing_token:
        _srv()._upsert_env_secret(_srv()._profile_dir(prof) / ".env", env_var, token)
    if _srv()._is_runtime_profile_slug(prof):
        _ensure_profile_llm_proxy(prof, provider)
        _sync_profile_model_api_key(prof, token)
    return token


def _action_proxy_base_url(provider_id: str) -> str:
    base = str(_srv().WORKFRAME_LLM_PROXY_INTERNAL or "http://workframe-api:8080").rstrip("/")
    return f"{base}/internal/action/{str(provider_id or '').strip().lower()}"


def _action_proxy_env_var(provider_id: str) -> str:
    return {
        "github": "GITHUB_API_URL",
        "vercel": "VERCEL_API_URL",
        "netlify": "NETLIFY_API_URL",
    }.get(str(provider_id or "").strip().lower(), "")


def _user_action_env_specs() -> list[tuple[str, str]]:
    specs: list[tuple[str, str]] = []
    for row in provider_catalog.PROVIDER_CONNECT_CATALOG:
        if not row.get("user_only"):
            continue
        for env_var in provider_catalog.provider_env_vars(row):
            specs.append((str(row["id"]), env_var))
    return specs


_USER_ACTION_CRED_CACHE: dict[tuple[str, str], tuple[bool, float]] = {}
_USER_ACTION_CRED_TTL_SEC = 30.0


def _user_has_action_credentials(user_id: str, workspace_id: str) -> bool:
    """Cached negative scan — skip per-turn tool overlay when user has no PAT/OAuth tools."""
    user = str(user_id or "").strip()
    if not user:
        return False
    ws = str(workspace_id or "").strip()
    key = (user, ws)
    now = time.monotonic()
    cached = _USER_ACTION_CRED_CACHE.get(key)
    if cached and now - cached[1] < _USER_ACTION_CRED_TTL_SEC:
        return cached[0]
    has_any = False
    for provider_id, _env_var in _user_action_env_specs():
        resolved = _srv()._resolve_credential(user, ws, provider_id, user_only=True)
        if resolved and _srv()._credential_secret(resolved, user):
            has_any = True
            break
    _USER_ACTION_CRED_CACHE[key] = (has_any, now)
    return has_any


def _overlay_turn_user_env(profile: str, user_id: str, workspace_id: str, run_id: str = "") -> None:
    """Issue per-run lease tokens for user-only tool credentials (never raw PATs on Agents mount)."""
    user = str(user_id or "").strip()
    if not user:
        return
    if not _user_has_action_credentials(user, workspace_id):
        return
    base_run = str(run_id or "").strip() or str(uuid.uuid4())
    for provider_id, _env_var in _user_action_env_specs():
        sub_run = f"{base_run}::{provider_id}"
        try:
            _apply_action_credential_lease(profile, user, workspace_id, provider_id, sub_run)
        except ValueError:
            continue


def _apply_action_credential_lease(
    profile: str,
    user_id: str,
    workspace_id: str,
    provider_id: str,
    run_id: str,
) -> str | None:
    """Lease token for user-only dev tools; upstream secret stays in API vault."""
    provider_id = str(provider_id or "").strip().lower()
    user = str(user_id or "").strip()
    run_id = str(run_id or "").strip()
    if not user or not provider_id or not run_id:
        return None
    prof = _srv().resolve_hermes_profile(profile)
    resolved = _srv()._resolve_credential(user, workspace_id, provider_id, user_only=True)
    if not resolved:
        return None
    if not _srv()._credential_secret(resolved, user):
        return None
    binding_id = str(
        resolved.get("credential_binding_id") or resolved.get("credential_id") or ""
    ).strip()
    if not binding_id:
        binding_id = str(uuid.uuid4())
        credential_vault.store_secret(
            binding_id,
            _srv()._credential_secret(resolved, user),
            env_var=str(resolved.get("env_var") or "") or _srv()._provider_env_var(provider_id),
            provider=provider_id,
            scope="user",
            user_id=user,
            workspace_id=workspace_id,
        )
    token = turn_credentials.issue_lease(
        run_id,
        user,
        workspace_id,
        provider_id,
        prof,
        binding_id or None,
    )
    env_var = str(resolved.get("env_var") or "") or _srv()._provider_env_var(provider_id)
    env_path = _srv()._profile_dir(prof) / ".env"
    _srv()._upsert_env_secret(env_path, env_var, token)
    proxy_env = _action_proxy_env_var(provider_id)
    if proxy_env:
        _srv()._upsert_env_secret(env_path, proxy_env, _action_proxy_base_url(provider_id))
    return token


def _revoke_turn_credential_lease(run_id: str, profile: str) -> None:
    """Revoke lease in DB; clear stale bearer from runtime profile config/gateway."""
    run_id = str(run_id or "").strip()
    if not run_id:
        return
    turn_credentials.revoke_lease(run_id)
    for provider_id, _env_var in _user_action_env_specs():
        turn_credentials.revoke_lease(f"{run_id}::{provider_id}")
    prof = _srv().resolve_hermes_profile(profile)
    if not _srv()._is_runtime_profile_slug(prof):
        return
    config_key = _read_config_model_api_key(prof)
    if config_key.startswith(turn_credentials.LEASE_PREFIX):
        _clear_profile_model_api_key(prof)
        _srv()._restart_runtime_profile_gateway(prof)


def _require_user_provider(user_id: str, workspace_id: str, provider: str) -> dict[str, Any]:
    """LLM billing uses the signed-in user's key only â€” same rule for chat and runtime agents."""
    return _require_runtime_owner_provider(user_id, workspace_id, provider)


def _require_runtime_owner_provider(user_id: str, workspace_id: str, provider: str) -> dict[str, Any]:
    provider = str(provider or "openrouter").strip().lower()
    oauth_spec = _srv()._oauth_llm_provider_spec(provider)
    if oauth_spec and _srv()._hermes_oauth_tokens_present(user_id, _srv()._hermes_auth_id_for_spec(oauth_spec)):
        hermes_auth_id = _srv()._hermes_auth_id_for_spec(oauth_spec)
        return {
            "credential_binding_id": None,
            "credential_id": None,
            "credential_ref": f"oauth:{hermes_auth_id}",
            "scope": "user",
            "provider": provider,
            "credential_type": "oauth",
            "label": hermes_auth_id,
            "env_var": "",
            "user_id": user_id,
            "workspace_id": None,
            "agent_profile_id": None,
            "created_by": user_id,
            "created_at": None,
            "updated_at": None,
            "expires_at": None,
        }
    resolved = _srv()._resolve_credential(user_id, workspace_id, provider, user_only=True)
    if resolved and _srv()._credential_secret(resolved, user_id):
        return resolved
    if _srv()._workspace_credential_mode(None, workspace_id) != "workspace":
        raise ValueError(
            "no_llm_provider_for_user: Connect an LLM provider under Profile â†’ Connected accts before chatting with agents."
        )
    resolved = _srv()._resolve_credential(user_id, workspace_id, provider, user_only=False)
    if resolved and _srv()._credential_secret(resolved, user_id):
        return resolved
    raise ValueError(
        "no_llm_provider_for_user: Connect an LLM provider under Profile â†’ Connected accts before chatting with agents."
    )


def _strip_profile_llm_env(profile: str, *, include_leases: bool = False) -> bool:
    """Remove shared-stack LLM keys from specialist profile .env."""
    try:
        prof = _srv().resolve_hermes_profile(profile)
    except ValueError:
        return False
    if prof == _srv()._primary_profile() and not _srv()._is_runtime_profile_slug(prof):
        return False
    path = _srv()._profile_dir(prof) / ".env"
    if not path.is_file():
        return False
    drop = set(_srv()._llm_provider_env_vars())
    kept: list[str] = []
    changed = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.partition("=")[0].strip()
            _val = line.partition("=")[2].strip().strip('"').strip("'")
            if include_leases and _val.startswith(turn_credentials.LEASE_PREFIX):
                changed = True
                continue
            if key in drop:
                # ponytail: keep active per-run lease tokens unless explicitly revoking
                if not include_leases and _val.startswith(turn_credentials.LEASE_PREFIX):
                    kept.append(line)
                    continue
                changed = True
                continue
        kept.append(line)
    if changed:
        path.write_text("\n".join(kept).rstrip() + ("\n" if kept else ""), encoding="utf-8")
    return changed


def _strip_profile_action_env(profile: str) -> bool:
    """Remove dev PAT tokens from specialist profile .env (never shared-stack keys)."""
    try:
        prof = _srv().resolve_hermes_profile(profile)
    except ValueError:
        return False
    if prof == _srv()._primary_profile() and not _srv()._is_runtime_profile_slug(prof):
        return False
    path = _srv()._profile_dir(prof) / ".env"
    if not path.is_file():
        return False
    drop = set()
    for _pid, env_var in _user_action_env_specs():
        drop.add(env_var)
    kept: list[str] = []
    changed = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.partition("=")[0].strip()
            if key in drop:
                changed = True
                continue
        kept.append(line)
    if changed:
        path.write_text("\n".join(kept).rstrip() + ("\n" if kept else ""), encoding="utf-8")
    return changed


def _overlay_turn_provider_env(
    profile: str,
    user_id: str,
    workspace_id: str,
    provider: str,
    run_id: str = "",
) -> str:
    """Per-run lease into profile env; upstream key resolved only inside workframe-api."""
    run_id = str(run_id or "").strip() or str(uuid.uuid4())
    # ponytail: yaml sync + gateway reload are async on the send path — never block TTFT (~40s).
    return _apply_turn_credential_lease(profile, user_id, workspace_id, provider, run_id)


def _try_overlay_turn_provider_env(
    profile: str,
    user_id: str,
    workspace_id: str,
    provider: str,
    run_id: str = "",
) -> bool:
    """Best-effort LLM lease; returns False when the user has no key yet."""
    try:
        _overlay_turn_provider_env(profile, user_id, workspace_id, provider, run_id)
        return True
    except ValueError as exc:
        if "no_llm_provider_for_user" in str(exc):
            return False
        raise


def _sync_profile_provider_env(profile: str, user_id: str = "", workspace_id: str = "") -> bool:
    """Copy the user's own LLM secrets into a specialist profile .env (never stack keys)."""
    prof = _srv().resolve_validated_profile(profile)
    if prof == _srv()._primary_profile():
        return False
    user = str(user_id or "").strip()
    if not user:
        return False

    target = _srv()._profile_dir(prof) / ".env"
    original = _srv()._read_env_map(target)
    merged = dict(original)
    needed = {key for key in _srv()._llm_provider_env_vars() if not merged.get(key)}
    if not needed:
        return False

    for key, value in _srv()._read_env_map(_srv()._user_hermes_env_path(user)).items():
        if key in needed and value:
            merged[key] = value
            needed.discard(key)
    if merged == original:
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(f"{key}={merged[key]}" for key in sorted(merged)) + "\n", encoding="utf-8")
    return True
