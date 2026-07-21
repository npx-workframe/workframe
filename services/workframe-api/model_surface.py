"""WF-032 extract: model_surface."""
from __future__ import annotations

import json
import os
import queue
import re
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

import provider_model_catalog
import profile_config_yaml
import user_prefs


def _srv():
    import server as srv

    return srv


def _resolve_models_profile(profile: str) -> str:
    """Hermes profile slug for model picker reads. Models belong to agent templates."""
    raw = str(profile or "").strip()
    if not raw:
        return _srv()._primary_profile()
    slug = _srv().safe_profile_slug(raw)
    if _srv()._is_runtime_profile_slug(slug):
        return _srv().resolve_validated_profile(_srv()._runtime_template_slug(slug))
    return _srv().resolve_validated_profile(slug)


def _agent_model_profile(profile: str) -> str:
    """Canonical write target for an agent's provider/model configuration."""
    raw = str(profile or _srv()._primary_profile()).strip()
    if not raw:
        return ""
    slug = _srv().safe_profile_slug(raw)
    if _srv()._is_runtime_profile_slug(slug):
        slug = _srv()._runtime_template_slug(slug)
    return _srv().resolve_validated_profile(slug)


def _model_suggestion_row(
    model_id: str,
    *,
    provider_label: str = "OpenRouter",
    billing_provider: str = "",
    label: str = "",
    description: str = "",
) -> dict[str, str]:
    slug = model_id.rsplit("/", 1)[-1] if "/" in model_id else model_id
    row = {
        "provider": provider_label,
        "model": model_id,
        "label": label or slug,
        "description": description or model_id,
    }
    if billing_provider:
        row["billing_provider"] = billing_provider
    return row


def _model_suggestion_key(row: dict[str, str]) -> tuple[str, str]:
    provider = str(row.get("billing_provider") or row.get("provider") or "").strip().lower()
    return provider, str(row.get("model") or "").strip()


def _augment_model_suggestions(
    suggestions: list[dict[str, str]],
    block: dict[str, Any],
) -> list[dict[str, str]]:
    """Ensure active primary and fallback chain models appear in the picker."""
    seen = {_model_suggestion_key(row) for row in suggestions}
    extra: list[dict[str, str]] = []
    primary = str(block.get("default") or "").strip()
    base_url = str(block.get("base_url") or "").strip()
    configured_provider = str(block.get("provider") or "").strip()
    bill = _billing_provider_from_block(base_url, configured_provider, configured_provider)
    if primary and (bill.lower(), primary) not in seen:
        extra.append(
            _model_suggestion_row(
                primary,
                provider_label=_srv()._provider_display_label(bill),
                billing_provider=bill,
                label=primary.rsplit("/", 1)[-1],
                description="Active model for this agent profile",
            ),
        )
        seen.add((bill.lower(), primary))
    for entry in block.get("fallback_chain") or []:
        if not isinstance(entry, dict):
            continue
        model = str(entry.get("model") or "").strip()
        prov = str(entry.get("provider") or "openrouter").strip()
        if not model:
            continue
        full = model if "/" in model else f"{prov}/{model}"
        bill = _billing_provider_from_block(base_url, prov, prov)
        if (bill.lower(), full) in seen:
            continue
        extra.append(
            _model_suggestion_row(
                full,
                provider_label=_srv()._provider_display_label(bill),
                billing_provider=bill,
                label=model.rsplit("/", 1)[-1],
                description="Configured in this profile's fallback chain",
            ),
        )
        seen.add((bill.lower(), full))
    return extra + suggestions


_INTERNAL_LLM_PROXY_RE = re.compile(r"/internal/llm/([a-z0-9_-]+)/v1", re.I)


def _billing_provider_from_block(base_url: str, cfg_provider: str, hint: str) -> str:
    """Pure resolver: the billing provider is the proxy URL segment (the stored fact).

    Order: explicit hint > proxy URL segment > cfg_provider > "openrouter".
    The model-id prefix (e.g. ``google/`` in ``google/gemini-2.5-flash``) is an
    OpenRouter vendor namespace, NOT a billing provider, so it is never used here.
    ponytail: removing model-prefix inference is the root-cause fix for the
    "provider not recognized" bug where an OpenRouter-only user was billed to google.
    """
    h = str(hint or "").strip().lower()
    mapped_hint = _billing_provider_id_from_hermes_config(h)
    if mapped_hint:
        return mapped_hint
    if h and h not in {"custom", "auto"}:
        return h.replace("_", "-")
    m = _INTERNAL_LLM_PROXY_RE.search(str(base_url or ""))
    if m:
        return m.group(1).lower()
    cfg = str(cfg_provider or "").strip().lower()
    mapped_cfg = _billing_provider_id_from_hermes_config(cfg)
    if mapped_cfg:
        return mapped_cfg
    if cfg and cfg not in {"custom", "auto"}:
        return cfg.replace("_", "-")
    return "openrouter"


def _normalized_profile_fallback_chain(
    block: dict[str, Any],
    default_billing_provider: str,
) -> list[dict[str, str]]:
    """Expose billing providers, not Hermes' internal ``custom`` transport."""
    base_url = str(block.get("base_url") or "").strip()
    normalized: list[dict[str, str]] = []
    for entry in block.get("fallback_chain") or []:
        if not isinstance(entry, dict):
            continue
        model = str(entry.get("model") or "").strip()
        configured = str(entry.get("provider") or "").strip()
        if not model:
            continue
        provider = _billing_provider_from_block(base_url, configured, configured)
        normalized.append({
            "provider": provider or default_billing_provider,
            "model": model,
        })
    return normalized


def _llm_billing_provider(
    profile: str,
    provider_hint: str = "",
    *,
    user_id: str = "",
    workspace_id: str = "",
    block: dict[str, Any] | None = None,
) -> str:
    """Map Hermes routing provider (often custom for proxy) to vault/billing provider id."""
    prof = _srv().resolve_hermes_profile(profile)
    block = block if block is not None else _read_model_block(prof)
    cfg_provider = str(block.get("provider") or "").strip().lower()
    billing_cfg = _billing_provider_id_from_hermes_config(cfg_provider)
    user = str(user_id or "").strip()
    ws = str(workspace_id or "").strip()
    if billing_cfg and user and _srv()._user_can_use_llm(user, ws, billing_cfg):
        return billing_cfg
    candidate = _billing_provider_from_block(
        str(block.get("base_url") or ""), cfg_provider, provider_hint,
    )
    # Provider/model are agent-owned. Credential availability decides whether
    # the acting user may run the agent; it must never silently reroute the
    # agent to a different provider and create DM/room drift.
    return candidate or "openrouter"


def _profile_llm_proxy_matches_billing(profile: str, billing_provider: str) -> bool:
    prof = _srv().resolve_hermes_profile(profile)
    base = str(_read_model_block(prof).get("base_url") or "").strip()
    return bool(base) and base == _srv()._llm_proxy_base_url(billing_provider)


def _profile_routing_matches_billing(
    prof: str,
    billing: str,
    *,
    block: dict[str, Any] | None = None,
) -> bool:
    """True when config.yaml already routes through the requested billing provider."""
    billing = str(billing or "").strip().lower()
    if not billing:
        return False
    block = block if block is not None else _read_model_block(prof)
    model = str(block.get("default") or "").strip()
    if not model:
        return False
    cfg = str(block.get("provider") or "").strip().lower()
    if _srv()._oauth_llm_provider_spec(billing):
        return cfg == _hermes_config_provider_id(billing).lower()
    if cfg != "custom":
        return False
    return _srv()._profile_llm_proxy_matches_billing(prof, billing)

# Canonical 3-tier model chain. `primary` is what new sessions resolve to;
# the fallback list kicks in when the primary fails (rate limit, 5xx,
# timeout). Order matters — Hermes tries them in sequence. Per-profile
# overrides live in the profile's config.yaml under `model.default` and
# `fallback_providers`; this constant is the install-wide default the
# migration writes when a profile is missing either field.
HERMES_DEFAULT_PRIMARY = "google/gemini-2.5-flash"
HERMES_DEFAULT_FALLBACK_CHAIN: list[dict[str, str]] = [
    {"provider": "openrouter", "model": "anthropic/claude-sonnet-4.5"},
    {"provider": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct:free"},
]

# ponytail: minimum-viable agentic models per LLM provider; user can escalate in settings.
PROVIDER_MVP_MODELS: dict[str, dict[str, Any]] = {
    "openrouter": {
        "primary": "google/gemini-2.5-flash",
        "fallbacks": list(HERMES_DEFAULT_FALLBACK_CHAIN),
    },
    "openai": {
        "primary": "gpt-5.4-medium",
        "fallbacks": [{"provider": "openai", "model": "gpt-4o-mini"}],
    },
    "anthropic": {
        "primary": "claude-sonnet-4-5",
        "fallbacks": [{"provider": "anthropic", "model": "claude-3-5-haiku-20241022"}],
    },
    "google": {
        "primary": "gemini-2.5-flash",
        "fallbacks": [{"provider": "google", "model": "gemini-2.5-flash-lite"}],
    },
    "deepseek": {
        "primary": "deepseek-chat",
        "fallbacks": [{"provider": "deepseek", "model": "deepseek-chat"}],
    },
    "codex": {
        "primary": "gpt-5.4-mini",
        "fallbacks": [
            {"provider": "openai-codex", "model": "gpt-5.4-mini"},
        ],
    },
    "nous": {
        "primary": "nousresearch/hermes-4-70b",
        "fallbacks": [{"provider": "nous", "model": "nousresearch/hermes-4-70b"}],
    },
}


# ponytail: billing id (connect catalog) ↔ Hermes config model.provider ↔ picker rows
_PROVIDER_CATALOG_TAGS: dict[str, frozenset[str]] = {
    # ChatGPT-account Codex has a narrower model surface than direct OpenAI API.
    "codex": frozenset({"codex"}),
    "openai": frozenset({"openai"}),
    "openrouter": frozenset({"openrouter"}),
    "anthropic": frozenset({"anthropic"}),
    "google": frozenset({"google"}),
    "deepseek": frozenset({"deepseek"}),
    "nous": frozenset({"nous"}),
}

_CODEX_EXTRA_MODELS: tuple[tuple[str, str, str], ...] = (
    ("gpt-5.4-mini", "GPT-5.4 Mini", "Faster Codex model on ChatGPT account."),
)


def _billing_provider_id_from_hermes_config(cfg_provider: str) -> str:
    p = str(cfg_provider or "").strip().lower()
    if p in {"openai-codex", "openai_codex", "codex"}:
        return "codex"
    if p in PROVIDER_MVP_MODELS:
        return p
    return ""


def _catalog_tags_for_billing_provider(provider_id: str) -> frozenset[str]:
    return _PROVIDER_CATALOG_TAGS.get(str(provider_id or "").strip().lower(), frozenset())


def _catalog_row_for_billing_provider(row: dict[str, str], provider_id: str) -> bool:
    tags = _catalog_tags_for_billing_provider(provider_id)
    if not tags:
        return False
    row_tag = str(row.get("provider") or "").strip().lower()
    return row_tag in tags


def _provider_display_label(provider_id: str) -> str:
    spec = _srv()._catalog_provider(provider_id) or {}
    return str(spec.get("label") or provider_id).strip() or provider_id


def _model_catalog_rows_for_provider(provider_id: str) -> list[dict[str, str]]:
    """Curated models a connected billing provider can run."""
    provider_key = str(provider_id or "").strip().lower()
    label = _srv()._provider_display_label(provider_key)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(model: str, row_label: str, description: str) -> None:
        mid = str(model or "").strip()
        if not mid or mid in seen:
            return
        seen.add(mid)
        rows.append(
            {
                "provider": provider_key,
                "billing_provider": provider_key,
                "model": mid,
                "label": row_label,
                "description": description,
            }
        )

    if provider_key == "codex":
        for model, row_label, description in _CODEX_EXTRA_MODELS:
            _add(model, row_label, description)
    mvp = PROVIDER_MVP_MODELS.get(provider_key) or {}
    primary = str(mvp.get("primary") or "").strip()
    if primary:
        _add(primary, primary, f"Default for {label}.")
    for fb in mvp.get("fallbacks") or []:
        if isinstance(fb, dict):
            _add(str(fb.get("model") or ""), str(fb.get("model") or ""), f"Fallback for {label}.")
    for row in HERMES_MODEL_CATALOG:
        if _catalog_row_for_billing_provider(row, provider_key):
            _add(
                str(row.get("model") or ""),
                str(row.get("label") or row.get("model") or ""),
                str(row.get("description") or ""),
            )
    return rows


def _suggestions_for_connected_llm_providers(connected: set[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for provider_id in sorted(connected):
        for row in _model_catalog_rows_for_provider(provider_id):
            mid = str(row.get("model") or "").strip()
            if not mid or mid in seen:
                continue
            seen.add(mid)
            out.append(row)
    return out


def _live_suggestions_for_connected_llm_providers(
    user_id: str,
    workspace_id: str,
    connected: set[str],
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    """Discover the models each effective credential can use right now."""
    credentials: dict[str, str] = {}
    for provider in sorted(connected):
        spec = _srv()._catalog_provider_for_llm(provider) or {}
        if str(spec.get("connect_mode") or "") == "oauth":
            auth_id = str(spec.get("hermes_auth_id") or provider)
            auth = _srv()._load_user_hermes_auth(user_id) if user_id else None
            credentials[provider] = provider_model_catalog.oauth_access_token(auth, auth_id)
            continue
        resolved = _srv()._resolve_credential(
            user_id,
            workspace_id,
            provider,
            user_only=_srv()._provider_user_only(provider),
        )
        credentials[provider] = _srv()._credential_secret(resolved or {}, user_id) if resolved else ""
    return provider_model_catalog.discover_many(credentials, timeout=8)


def _default_model_from_live_catalog(
    connected: set[str],
    suggestions: list[dict[str, str]],
) -> tuple[str, str]:
    """Choose a valid default from the first effective provider, never a disconnected one."""
    catalog_order = [
        str(spec["id"]).lower()
        for spec in _srv().PROVIDER_CONNECT_CATALOG
        if str(spec.get("category") or "") == "llm"
        and str(spec["id"]).lower() in connected
    ]
    for provider in catalog_order:
        rows = [
            row for row in suggestions
            if str(row.get("billing_provider") or row.get("provider") or "").strip().lower() == provider
        ]
        if not rows:
            continue
        preferred = str((PROVIDER_MVP_MODELS.get(provider) or {}).get("primary") or "").strip()
        if preferred and any(str(row.get("model") or "") == preferred for row in rows):
            return preferred, provider
        return str(rows[0].get("model") or "").strip(), provider
    return "", ""


def _effective_fallback_chain(chain: list[dict[str, str]], connected: set[str]) -> list[dict[str, str]]:
    effective: list[dict[str, str]] = []
    for entry in chain:
        if not isinstance(entry, dict):
            continue
        provider = _billing_provider_id_from_hermes_config(str(entry.get("provider") or "")) or str(
            entry.get("provider") or ""
        ).strip().lower()
        model = str(entry.get("model") or "").strip()
        if provider in connected and model:
            effective.append({"provider": provider, "model": model})
    return effective


def _model_id_vendor_and_bare(model_id: str) -> tuple[str, str]:
    """Split vendor/model ids (e.g. openai-codex/gpt-5.4-mini) into billing + bare model."""
    mid = str(model_id or "").strip()
    if "/" not in mid:
        return "", mid
    prefix, bare = mid.split("/", 1)
    billing = _billing_provider_id_from_hermes_config(prefix)
    return billing, bare.strip()


def _persisted_model_id(model_id: str, billing: str) -> str:
    billing = str(billing or "").strip().lower()
    _, bare = _model_id_vendor_and_bare(model_id)
    if _srv()._oauth_llm_provider_spec(billing) and bare:
        return bare
    return str(model_id or "").strip()


def _apply_model_persisted(
    profile: str,
    billing: str,
    model_id: str,
    user_id: str = "",
    *,
    restart_gateway: bool = True,
) -> tuple[bool, str]:
    """Write model surface and verify default landed on disk before returning ok."""
    prof = _srv().resolve_hermes_profile(profile)
    billing = str(billing or "").strip().lower()
    if billing:
        if not _apply_model_for_billing_provider(prof, billing, model_id, user_id=user_id):
            return False, "model apply failed"
    else:
        ok, err = _set_profile_model(prof, model_id)
        if not ok:
            return False, err or "model apply failed"
    expected = _persisted_model_id(model_id, billing)
    got = str(_parse_model_block_from_disk(prof).get("default") or "").strip()
    if expected and got != expected:
        return False, f"model not persisted (expected {expected}, got {got or 'empty'})"
    if restart_gateway and _srv()._is_runtime_profile_slug(prof):
        _srv()._reload_runtime_profile_gateway(prof, wait_healthy=True)
    return True, ""


def _mirror_template_model_to_runtime(
    user_id: str,
    template_slug: str,
    billing: str,
    model_id: str,
) -> tuple[bool, str]:
    """After a template model save, apply the same pick to the user's runtime profile."""
    user = str(user_id or "").strip()
    template = _srv().safe_profile_slug(template_slug)
    if not user or _srv()._is_runtime_profile_slug(template):
        return True, ""
    runtime = _srv()._runtime_profile_slug(user, template)
    if not _srv()._runtime_profile_on_disk(runtime):
        return True, ""
    return _apply_model_persisted(
        runtime, billing, model_id, user_id=user, restart_gateway=False,
    )


def _sync_agent_model_to_runtimes(
    template_slug: str,
    *,
    current_user_id: str = "",
    current_workspace_id: str = "",
) -> tuple[bool, str, list[str]]:
    """Mirror one agent model surface to every existing per-user runtime.

    Runtime profiles isolate credentials and gateways, not agent preferences.
    Owner-specific credentials are refreshed when their identity is resolvable.
    """
    template = _agent_model_profile(template_slug)
    if not template:
        return False, "no profile resolved", []
    profiles_dir = _srv().HERMES_DATA / "profiles"
    runtimes: set[str] = set()
    if profiles_dir.is_dir():
        for path in profiles_dir.iterdir():
            if not path.is_dir() or not _srv()._is_runtime_profile_slug(path.name):
                continue
            try:
                if _srv()._runtime_template_slug(path.name) == template:
                    runtimes.add(path.name)
            except ValueError:
                continue
    user = str(current_user_id or "").strip()
    if user:
        candidate = _srv()._runtime_profile_slug(user, template)
        if _srv()._runtime_profile_on_disk(candidate):
            runtimes.add(candidate)

    synced: list[str] = []
    for runtime in sorted(runtimes):
        owner = _srv()._resolve_runtime_owner(runtime)
        owner_id = str(owner[0] if owner else "").strip()
        workspace_id = str(owner[1] if owner else "").strip()
        if not owner_id and user and runtime == _srv()._runtime_profile_slug(user, template):
            owner_id = user
            workspace_id = str(current_workspace_id or "").strip()
        ok, err = _sync_runtime_model_from_template(
            runtime,
            template,
            user_id=owner_id,
        )
        if not ok:
            return False, err or f"runtime model sync failed: {runtime}", synced
        if owner_id:
            _srv()._prepare_runtime_profile_credentials(
                runtime,
                owner_id,
                workspace_id,
                wait_healthy=False,
            )
        _srv()._schedule_gateway_reload(runtime)
        synced.append(runtime)
    return True, "", synced


def _resolve_billing_provider_for_model(
    model_id: str,
    connected: set[str],
    *,
    prefer: str = "",
) -> str:
    mid = str(model_id or "").strip()
    if not mid or not connected:
        return ""
    vendor, bare = _model_id_vendor_and_bare(mid)
    if vendor and vendor in connected:
        return vendor
    match_ids = [mid]
    if bare and bare not in match_ids:
        match_ids.append(bare)
    pref = str(prefer or "").strip().lower()
    if pref and pref in connected:
        for row in _model_catalog_rows_for_provider(pref):
            row_model = str(row.get("model") or "").strip()
            if row_model in match_ids:
                return pref
    for provider_id in sorted(connected):
        for row in _model_catalog_rows_for_provider(provider_id):
            row_model = str(row.get("model") or "").strip()
            if row_model in match_ids:
                return provider_id
    low = (bare or mid).lower()
    if low.startswith("gpt-") and "codex" in connected:
        return "codex"
    if low.startswith("gpt-") and "openai" in connected:
        return "openai"
    if "/" in mid and "openrouter" in connected:
        prefix = mid.split("/", 1)[0].strip().lower()
        if not _billing_provider_id_from_hermes_config(prefix):
            return "openrouter"
    if low.startswith("claude") and "anthropic" in connected:
        return "anthropic"
    if "gemini" in low and "google" in connected:
        return "google"
    if "deepseek" in low and "deepseek" in connected:
        return "deepseek"
    return ""


def _strip_profile_model_proxy_fields(profile: str) -> None:
    """OAuth/native providers: drop internal proxy base_url + lease api_key from model block."""
    config_path = _srv()._profile_gateway_config_path(profile)
    if not config_path or not config_path.is_file():
        return
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return
    out: list[str] = []
    in_model = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("model:") and not line.startswith((" ", "\t")):
            in_model = True
            out.append(line)
            continue
        if in_model and stripped and not line.startswith((" ", "\t", "#")):
            in_model = False
        if in_model and stripped.startswith(("base_url:", "api_key:")):
            continue
        out.append(line)
    try:
        config_path.write_text("".join(out), encoding="utf-8")
    except OSError:
        return


def _apply_model_for_billing_provider(
    profile: str,
    billing: str,
    model_id: str,
    user_id: str = "",
) -> bool:
    billing = str(billing or "").strip().lower()
    _, bare = _model_id_vendor_and_bare(model_id)
    if _srv()._oauth_llm_provider_spec(billing) and bare:
        model_id = bare
    ok, _ = _set_profile_model(profile, model_id)
    if not ok:
        return False
    if _srv()._oauth_llm_provider_spec(billing):
        ok_provider, _ = _set_profile_model_provider(profile, _hermes_config_provider_id(billing))
        if not ok_provider:
            return False
        _strip_profile_model_proxy_fields(profile)
        fallbacks = PROVIDER_MVP_MODELS.get(billing, {}).get("fallbacks") or []
        if isinstance(fallbacks, list):
            chain = _read_model_block(profile).get("fallback_chain") or []
            if not chain:
                _write_fallback_chain(profile, fallbacks)
        user = str(user_id or "").strip()
        if user:
            _srv()._sync_oauth_llm_to_profile(profile, user, billing)
        return True
    ok_provider, _ = _set_profile_model_provider(profile, "custom")
    if not ok_provider:
        return False
    _srv()._set_profile_model_base_url(profile, _srv()._llm_proxy_base_url(billing))
    return True


def _hermes_config_provider_id(provider_key: str) -> str:
    spec = _srv()._catalog_provider(provider_key)
    if spec and spec.get("hermes_auth_id"):
        return str(spec["hermes_auth_id"])
    return str(provider_key or "").strip().lower()


def _first_connected_llm_provider(user_id: str = "", workspace_id: str = "") -> str:
    for spec in _srv().PROVIDER_CONNECT_CATALOG:
        if str(spec.get("category") or "") != "llm":
            continue
        provider_id = str(spec["id"])
        if user_id and _user_provider_connected(str(user_id), spec):
            return provider_id
        if workspace_id and str(spec.get("env_var") or ""):
            resolved = _srv()._resolve_credential("", str(workspace_id), provider_id)
            if resolved and _srv()._credential_secret(resolved, str(user_id or "")):
                return provider_id
    return "openrouter"


def _apply_mvp_model_for_provider(profile: str, provider: str) -> bool:
    """Write model.default, model.provider, and fallback_providers to config.yaml."""
    provider_key = str(provider or "openrouter").strip().lower()
    spec = PROVIDER_MVP_MODELS.get(provider_key) or PROVIDER_MVP_MODELS["openrouter"]
    try:
        _srv()._ensure_gateway_config_file(profile)
    except ValueError:
        return False
    ok, _ = _set_profile_model(profile, str(spec["primary"]))
    if not ok:
        return False
    ok_provider, _ = _set_profile_model_provider(profile, _hermes_config_provider_id(provider_key))
    fallbacks = spec.get("fallbacks") if isinstance(spec.get("fallbacks"), list) else []
    ok_chain, _ = _write_fallback_chain(profile, fallbacks)
    return ok_provider and ok_chain


def _bootstrap_model_after_llm_connect(
    user_id: str,
    workspace_id: str,
    provider: str,
) -> None:
    """Seed MVP model on runtime + primary profiles when an LLM key is connected."""
    spec = _srv()._catalog_provider(provider)
    if not spec or str(spec.get("category") or "") != "llm":
        return
    provider_key = str(provider or "").strip().lower()
    user = str(user_id or "").strip()
    ws = str(workspace_id or "").strip()
    primary = _srv()._primary_profile()
    if primary:
        if user and _srv()._oauth_llm_provider_spec(provider_key):
            _srv()._reconcile_profile_llm_for_user(primary, user, ws, prefer_provider=provider_key)
        else:
            _, model = _srv()._read_model_from_config(primary)
            if not str(model or "").strip():
                _apply_mvp_model_for_provider(primary, provider_key)
            elif user:
                _srv()._reconcile_profile_llm_for_user(primary, user, ws, prefer_provider=provider_key)
    template = primary or "workframe-agent"
    runtime = _srv()._runtime_profile_slug(user_id, template)
    if _srv()._runtime_profile_on_disk(runtime):
        if user and _srv()._oauth_llm_provider_spec(provider_key):
            _srv()._reconcile_profile_llm_for_user(runtime, user, ws, prefer_provider=provider_key)
        else:
            _, model = _srv()._read_model_from_config(runtime)
            if not str(model or "").strip():
                _apply_mvp_model_for_provider(runtime, provider_key)
            elif user:
                _srv()._reconcile_profile_llm_for_user(runtime, user, ws, prefer_provider=provider_key)
    if user:
        _srv()._refresh_user_runtime_credentials(user, ws, wait_healthy=False)
    elif ws:
        _srv()._refresh_workspace_runtime_credentials(ws, wait_healthy=False)


# Curated snapshot of commonly-used models per provider. Surfaced in the
# Workframe picker as suggestions — the BFF also accepts arbitrary
# `provider/model` ids so users aren't boxed in. The picker shows this
# list ONLY for the active provider; cross-provider entries are hidden
# because they need the matching API key in env to actually work.
HERMES_MODEL_CATALOG: list[dict[str, str]] = [
    {"provider": "Anthropic", "model": "claude-sonnet-4-5",
     "label": "Claude Sonnet 4.5",
     "description": "Latest Sonnet. Strong general purpose."},
    {"provider": "Anthropic", "model": "claude-opus-4-1",
     "label": "Claude Opus 4.1",
     "description": "Heaviest reasoning. Slow but thorough."},
    {"provider": "Anthropic", "model": "claude-3-5-sonnet-20241022",
     "label": "Claude 3.5 Sonnet",
     "description": "Previous gen. Still very capable."},
    {"provider": "Anthropic", "model": "claude-3-5-haiku-20241022",
     "label": "Claude 3.5 Haiku",
     "description": "Fast and cheap."},
    {"provider": "OpenAI", "model": "gpt-5.4-medium",
     "label": "GPT-5.4 Medium", "description": "Workframe OpenAI default — agentic, tool-capable."},
    {"provider": "OpenAI", "model": "gpt-4o",
     "label": "GPT-4o", "description": "OpenAI flagship multimodal."},
    {"provider": "OpenAI", "model": "gpt-4o-mini",
     "label": "GPT-4o mini", "description": "Cheap, fast."},
    {"provider": "OpenAI", "model": "o1",
     "label": "o1", "description": "Reasoning model."},
    {"provider": "OpenAI", "model": "o1-mini",
     "label": "o1 mini", "description": "Cheaper reasoning."},
    {"provider": "OpenAI", "model": "gpt-5.4-mini",
     "label": "GPT-5.4 Mini", "description": "Faster Codex / OpenAI model."},
    {"provider": "Codex", "model": "gpt-5.4-mini",
     "label": "GPT-5.4 Mini (Codex)", "description": "Faster Codex model."},
    {"provider": "Google", "model": "gemini-2.5-pro",
     "label": "Gemini 2.5 Pro",
     "description": "Long context, strong reasoning."},
    {"provider": "Google", "model": "gemini-2.0-flash",
     "label": "Gemini 2.0 Flash", "description": "Fast, cheap."},
    {"provider": "DeepSeek", "model": "deepseek-chat",
     "label": "DeepSeek Chat",
     "description": "DeepSeek general chat model."},
    {"provider": "DeepSeek", "model": "deepseek-reasoner",
     "label": "DeepSeek Reasoner",
     "description": "Reasoning-focused DeepSeek model."},
    {"provider": "OpenRouter", "model": "openrouter/auto",
     "label": "OpenRouter Auto",
     "description": "OpenRouter picks the best model per prompt."},
    {"provider": "OpenRouter", "model": "google/gemini-2.5-flash",
     "label": "Gemini 2.5 Flash",
     "description": "Fast, capable default for OpenRouter BYOK."},
    {"provider": "OpenRouter", "model": "anthropic/claude-sonnet-4.5",
     "label": "Claude Sonnet 4.5 (via OR)",
     "description": "Strong agentic fallback on OpenRouter."},
    {"provider": "OpenRouter", "model": "meta-llama/llama-3.3-70b-instruct:free",
     "label": "Llama 3.3 70B (free)",
     "description": "Free-tier OpenRouter fallback when available."},
    {"provider": "OpenRouter", "model": "z-ai/glm-5.1",
     "label": "GLM 5.1",
     "description": "High-availability model on OpenRouter."},
    {"provider": "OpenRouter", "model": "nousresearch/hermes-4-70b",
     "label": "Hermes 4 70B",
     "description": "Agent-tuned model on OpenRouter."},
    {"provider": "OpenRouter", "model": "openrouter/nvidia/llama-3.1-nemotron-70b-instruct",
     "label": "Nemotron 70B Instruct",
     "description": "NVIDIA Nemotron via OpenRouter."},
    {"provider": "OpenRouter", "model": "openrouter/openai/gpt-4o",
     "label": "GPT-4o (via OR)",
     "description": "GPT-4o through OpenRouter."},
]


def _set_profile_model(profile: str, model_id: str) -> tuple[bool, str]:
    """Update `model.default` in config.yaml via profile_config_yaml."""
    _srv()._normalize_profile_config_yaml(profile)
    try:
        config_path = _srv()._ensure_gateway_config_file(profile)
    except ValueError as exc:
        return False, str(exc)
    try:
        profile_config_yaml.update_model_surface(config_path, default=model_id)
    except OSError as exc:
        return False, f"write failed: {exc}"
    return True, ""


def _set_profile_model_provider(profile: str, provider: str) -> tuple[bool, str]:
    _srv()._normalize_profile_config_yaml(profile)
    try:
        config_path = _srv()._ensure_gateway_config_file(profile)
    except ValueError as exc:
        return False, str(exc)
    provider = str(provider or "").strip().lower()
    if not provider:
        return False, "provider required"
    try:
        profile_config_yaml.update_model_surface(config_path, provider=provider)
    except OSError as exc:
        return False, f"write failed: {exc}"
    return True, ""


def _parse_model_block_from_disk(profile: str) -> dict[str, Any]:
    """Parse the model surface from the profile's config.yaml:
    `model.default`, `model.provider`, etc. (siblings of `model:`) AND
    the top-level `fallback_providers:` block. Pure text scan — no
    pyyaml in the image.
    """
    config_path = _srv()._profile_config_path(profile)
    empty: dict[str, Any] = {
        "default": "",
        "provider": "",
        "base_url": "",
        "api_mode": "",
        "api_key": "",
        "providers": {},
        "fallback_chain": [],
    }
    if not config_path:
        return empty
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return empty

    out = dict(empty)
    in_model = False
    in_fallback = False
    fallback_indent = -1
    fallback_item_indent = -1
    saw_top_model = False
    for raw in lines:
        stripped = raw.rstrip()
        if not stripped.strip() or stripped.lstrip().startswith("#"):
            continue
        indent = len(stripped) - len(stripped.lstrip())
        content = stripped.lstrip()

        # Track which top-level block we're in. The model block is the
        # `model:` section (indent 0 + `model:`); fallback_providers is
        # a SIBLING at indent 0, not nested under model.
        if indent == 0 and content.startswith("model:"):
            if saw_top_model:
                in_model = False
                continue
            saw_top_model = True
            in_model = True
            in_fallback = False
            continue
        if indent == 0:
            in_model = False

        # `model:` block: read its immediate sub-keys (default, provider,
        # base_url, api_mode). They sit at indent 2 with a `:`.
        if in_model and indent == 2 and ":" in content and not in_fallback:
            key, _, value = content.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key == "default":
                out["default"] = value
            elif key == "provider":
                out["provider"] = value
            elif key == "base_url":
                out["base_url"] = value
            elif key == "api_mode":
                out["api_mode"] = value
            elif key == "api_key":
                out["api_key"] = value
            continue

        # `fallback_providers:` is a top-level list. The key is at
        # indent 0; list items at indent 2 with `- `; sub-keys at
        # indent 4 (e.g. `model:` under the entry). An inline form like
        # `fallback_providers: []` or `{}` is empty; a bare
        # `fallback_providers:` (nothing after the colon) starts a
        # multi-line list and must NOT reset in_fallback.
        if indent == 0 and content.startswith("fallback_providers:"):
            in_fallback = True
            fallback_indent = indent
            fallback_item_indent = -1
            after = content.split(":", 1)[1].strip()
            if after and (
                after in {"{}", "[]"}
                or (after.startswith("{") and after.endswith("}"))
                or (after.startswith("[") and after.endswith("]"))
            ):
                in_fallback = False
            continue

        if (
            in_fallback
            and content.startswith("- ")
            and indent in {fallback_indent, fallback_indent + 2}
        ):
            # PyYAML emits root sequences without indentation by default,
            # while hand-authored configs commonly indent the same item.
            fallback_item_indent = indent
            inline = content[2:].strip()
            entry: dict[str, str] = {}
            if ":" in inline:
                k, _, v = inline.partition(":")
                entry[k.strip()] = v.strip().strip('"').strip("'")
            out["fallback_chain"].append(entry)
            continue

        if (
            in_fallback
            and fallback_item_indent >= 0
            and indent > fallback_item_indent
            and ":" in content
        ):
            k, _, v = content.partition(":")
            key = k.strip()
            val = v.strip().strip('"').strip("'")
            if out["fallback_chain"] and key in {"provider", "model", "base_url"}:
                out["fallback_chain"][-1][key] = val
            continue

        if in_fallback and indent == fallback_indent + 2 and ":" in content and not content.startswith("- "):
            # ponytail: wizard once wrote flat `model:` keys (no list) — tolerate one entry per line
            k, _, v = content.partition(":")
            key = k.strip()
            val = v.strip().strip('"').strip("'")
            if key == "model" and val:
                out["fallback_chain"].append({"model": val})
            continue

        if in_fallback and indent <= fallback_indent and not content.startswith("- "):
            # Exited the fallback block.
            in_fallback = False
    return out


def _read_model_block(profile: str) -> dict[str, Any]:
    """Model surface for a profile. Runtime u-* slugs inherit default/chain from template."""
    raw = str(profile or "").strip()
    if not raw:
        return _parse_model_block_from_disk("")
    try:
        prof = _srv().resolve_hermes_profile(raw)
    except ValueError:
        return _parse_model_block_from_disk(raw)
    block = _parse_model_block_from_disk(prof)
    if not _srv()._is_runtime_profile_slug(prof):
        return block
    # ponytail: runtime with model+provider on disk — skip template read on bind/chat hot path.
    if str(block.get("default") or "").strip() and str(block.get("provider") or "").strip():
        return block
    template = _srv().resolve_validated_profile(_srv()._runtime_template_slug(prof))
    tblock = _parse_model_block_from_disk(template)
    if not str(block.get("default") or "").strip() and str(tblock.get("default") or "").strip():
        block["default"] = tblock["default"]
    if not block.get("fallback_chain") and tblock.get("fallback_chain"):
        block["fallback_chain"] = list(tblock["fallback_chain"])
    tpl_provider = str(tblock.get("provider") or "").strip()
    if not str(block.get("provider") or "").strip() and tpl_provider:
        block["provider"] = tpl_provider
    return block


def _sync_runtime_model_from_template(
    runtime: str,
    template: str,
    *,
    user_id: str = "",
) -> tuple[bool, str]:
    """Keep a credential-isolated runtime aligned with its agent template."""
    runtime_slug = _srv().safe_profile_slug(runtime)
    template_slug = _srv().resolve_validated_profile(template)
    if not _srv()._is_runtime_profile_slug(runtime_slug) or not _srv().profile_exists(runtime_slug):
        return False, "runtime profile not installed"
    tblock = _parse_model_block_from_disk(template_slug)
    default = str(tblock.get("default") or "").strip()
    if not default:
        return False, "agent template has no model"
    configured_provider = str(tblock.get("provider") or "").strip()
    billing = _billing_provider_from_block(
        str(tblock.get("base_url") or ""),
        configured_provider,
        configured_provider,
    )
    ok, err = _apply_model_persisted(
        runtime_slug,
        billing,
        default,
        user_id=str(user_id or "").strip(),
        restart_gateway=False,
    )
    if not ok:
        return False, err
    chain = [e for e in (tblock.get("fallback_chain") or []) if isinstance(e, dict)]
    ok, err = _write_fallback_chain(runtime_slug, chain)
    if not ok:
        return False, err
    return True, ""


def _write_fallback_chain(profile: str, chain: list[dict[str, str]]) -> tuple[bool, str]:
    """Rewrite fallback_providers via profile_config_yaml (WF-033)."""
    _srv()._normalize_profile_config_yaml(profile)
    config_path = _srv()._profile_gateway_config_path(profile)
    if not config_path or not config_path.is_file():
        try:
            config_path = _srv()._ensure_gateway_config_file(profile)
        except ValueError as exc:
            return False, str(exc)
    normalized: list[dict[str, str]] = []
    for entry in chain:
        if not isinstance(entry, dict):
            continue
        provider = str(entry.get("provider", "")).strip()
        model = str(entry.get("model", "")).strip()
        if provider and model:
            normalized.append({"provider": provider, "model": model})
    try:
        profile_config_yaml.update_model_surface(config_path, fallback_chain=normalized)
    except OSError as exc:
        return False, f"write failed: {exc}"
    _srv()._normalize_profile_config_yaml(profile)
    return True, ""


def hermes_models(
    profile: str = "",
    user_id: str = "",
    workspace_id: str = "",
    *,
    selection_only: bool = False,
) -> dict[str, Any]:
    """Return a profile's model surface: primary, fallback chain,
    and curated suggestions scoped to the active provider. The catalog
    is a hint list, not a hardcoded menu — the BFF accepts any
    `provider/model` id and the picker always lets the user type a
    custom one.
    """
    picker_llm = _srv()._user_llm_providers_for_picker(user_id) if user_id else set()
    connected = _srv()._connected_provider_names(user_id, workspace_id)
    has_llm = _srv()._user_llm_has_provider(user_id, workspace_id) if user_id else any(
        str(spec.get("category") or "") == "llm"
        and str(spec.get("id")).lower() in {n.lower() for n in connected}
        for spec in _srv().PROVIDER_CONNECT_CATALOG
    )
    connected_llm = set(picker_llm) if user_id else {
        str(spec["id"]).lower()
        for spec in _srv().PROVIDER_CONNECT_CATALOG
        if str(spec.get("category") or "") == "llm"
        and str(spec.get("id")).lower() in {n.lower() for n in connected}
    }
    if user_id and workspace_id:
        connected_llm.update(
            str(spec["id"]).lower()
            for spec in _srv().PROVIDER_CONNECT_CATALOG
            if str(spec.get("category") or "") == "llm"
            and _srv()._user_can_use_llm(user_id, workspace_id, str(spec["id"]))
        )
    live_suggestions, catalog_status = (
        _live_suggestions_for_connected_llm_providers(user_id, workspace_id, connected_llm)
        if user_id and connected_llm
        else ([], {})
    )

    if selection_only:
        user_primary, user_chain = user_prefs.read_user_llm_prefs(user_id) if user_id else ("", [])
        primary = user_primary
        billing = _resolve_billing_provider_for_model(primary, connected_llm) if primary else ""
        if primary and not billing:
            primary = ""
        if not primary and has_llm:
            primary, billing = _default_model_from_live_catalog(connected_llm, live_suggestions)
        user_chain = _effective_fallback_chain(user_chain, connected_llm)
        suggestions = _augment_model_suggestions(
            live_suggestions,
            {
                "default": primary,
                "provider": billing or "",
                "base_url": "",
                "providers": {},
                "fallback_chain": user_chain,
            },
        )
        return {
            "ok": True,
            "profile": "",
            "primary": primary if has_llm else "",
            "provider": billing if has_llm else "",
            "base_url": "",
            "fallback_chain": user_chain if has_llm else [],
            "suggestions": suggestions,
            "connected_providers": sorted(connected_llm),
            "catalog_status": catalog_status,
            "has_llm_provider": has_llm,
            "billing_provider": billing if has_llm else "",
            "selection_only": True,
            "default_primary": HERMES_DEFAULT_PRIMARY,
            "default_fallback_chain": HERMES_DEFAULT_FALLBACK_CHAIN,
        }

    try:
        primary_profile = _resolve_models_profile(profile) if profile else _srv()._primary_profile()
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if primary_profile:
        _srv()._ensure_profile_auth_pool(primary_profile, user_id, workspace_id)
    block = _read_model_block(primary_profile) if primary_profile else {
        "default": "", "provider": "", "base_url": "",
        "providers": {}, "fallback_chain": [],
    }
    active_provider = block.get("provider", "").strip()
    primary_model = str(block.get("default") or "").strip()
    billing = _billing_provider_from_block(
        str(block.get("base_url") or ""),
        active_provider,
        active_provider,
    )
    if not billing and primary_model:
        billing = _resolve_billing_provider_for_model(primary_model, connected_llm) or ""
    if not billing and user_id and primary_profile:
        billing = _llm_billing_provider(
            primary_profile, user_id=user_id, workspace_id=workspace_id,
        )
    suggestions = _augment_model_suggestions(
        live_suggestions,
        {**block, "provider": billing or active_provider},
    )
    _, bare_primary = _model_id_vendor_and_bare(primary_model)
    if _srv()._oauth_llm_provider_spec(billing) and bare_primary:
        primary_model = bare_primary
    seen_models: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for row in suggestions:
        key = _model_suggestion_key(row)
        if not key[1] or key in seen_models:
            continue
        seen_models.add(key)
        deduped.append(row)
    suggestions = deduped
    display_provider = billing
    return {
        "ok": True,
        "profile": primary_profile,
        "primary": primary_model if has_llm else "",
        "provider": display_provider if has_llm else "",
        "base_url": block.get("base_url", ""),
        "fallback_chain": _normalized_profile_fallback_chain(block, billing) if has_llm else [],
        "suggestions": suggestions,
        "connected_providers": sorted(connected_llm),
        "catalog_status": catalog_status,
        "has_llm_provider": has_llm,
        "billing_provider": billing if has_llm else "",
        "default_primary": HERMES_DEFAULT_PRIMARY,
        "default_fallback_chain": HERMES_DEFAULT_FALLBACK_CHAIN,
    }


def hermes_apply_default_model_config() -> dict[str, Any]:
    """One-shot migration: every profile gets owl-alpha as the primary
    and the canonical 3-tier fallback chain. Idempotent — running it
    again produces the same state. Use after a fresh install or to
    recover from a profile whose config was hand-edited into a bad
    state.
    """
    profiles = _list_profiles()
    results: list[dict[str, str]] = []
    for profile in profiles:
        ok_model, err_model = _set_profile_model(profile, HERMES_DEFAULT_PRIMARY)
        ok_chain, err_chain = _write_fallback_chain(profile, HERMES_DEFAULT_FALLBACK_CHAIN)
        results.append({
            "profile": profile,
            "ok": "yes" if (ok_model and ok_chain) else "no",
            "error": err_model or err_chain or "",
        })
    return {
        "ok": True,
        "applied_to": [r["profile"] for r in results if r["ok"] == "yes"],
        "details": results,
    }


def hermes_model_set(
    profile: str,
    model_id: str,
    user_id: str = "",
    workspace_id: str = "",
    *,
    selection_only: bool = False,
    billing_provider: str = "",
) -> dict[str, Any]:
    """Set primary model and align Hermes provider routing to a connected billing provider."""
    user = str(user_id or "").strip()
    if selection_only:
        if not user:
            return {"ok": False, "error": "unauthorized"}
        connected = _srv()._user_llm_providers_for_picker(user)
        billing = str(billing_provider or "").strip().lower()
        if not billing:
            billing = _resolve_billing_provider_for_model(model_id, connected)
        if not billing and not _srv()._user_llm_has_provider(user, workspace_id):
            return {"ok": False, "error": "connect an LLM provider first"}
        user_prefs.write_user_llm_prefs(user, primary=model_id)
        return {
            "ok": True,
            "profile": "",
            "model": model_id,
            "provider": billing or "",
            "billing_provider": billing or "",
            "selection_only": True,
        }
    try:
        target = _agent_model_profile(profile)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if not target:
        return {"ok": False, "error": "no profile resolved"}
    if not model_id or " " in model_id or "\n" in model_id:
        return {"ok": False, "error": "invalid model id"}
    user = str(user_id or "").strip()
    ws = str(workspace_id or "").strip()
    connected = _srv()._user_llm_providers_for_picker(user) if user else set()
    billing = str(billing_provider or "").strip().lower()
    if not billing:
        prefer = _llm_billing_provider(target, user_id=user, workspace_id=ws) if target else ""
        billing = _resolve_billing_provider_for_model(model_id, connected, prefer=prefer)
    if billing:
        ok, err = _apply_model_persisted(
            target, billing, model_id, user, restart_gateway=False,
        )
        if not ok:
            return {"ok": False, "error": err}
    else:
        ok, err = _apply_model_persisted(
            target, "", model_id, user, restart_gateway=False,
        )
        if not ok:
            return {"ok": False, "error": err}
    block = _read_model_block(target)
    resolved_billing = billing or _billing_provider_id_from_hermes_config(
        str(block.get("provider") or "")
    ) or _llm_billing_provider(target, user_id=user, workspace_id=ws)
    persisted = _persisted_model_id(model_id, billing or resolved_billing)
    _srv()._sync_agent_profile_db(
        target,
        {"model_provider": resolved_billing, "model_name": persisted},
    )
    ok, err, synced_runtimes = _sync_agent_model_to_runtimes(
        target,
        current_user_id=user,
        current_workspace_id=ws,
    )
    if not ok:
        return {"ok": False, "error": err}
    _srv()._schedule_gateway_reload(target)
    return {
        "ok": True,
        "profile": target,
        "model": persisted,
        "provider": resolved_billing,
        "billing_provider": resolved_billing,
        "synced_runtimes": synced_runtimes,
    }


def hermes_fallback_chain_set(
    profile: str,
    chain: list[Any],
    *,
    selection_only: bool = False,
    user_id: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    """Set the fallback chain for a profile. Each entry must have
    `provider` and `model` keys. Order matters: Hermes tries them in
    sequence when the primary fails.
    """
    normalized: list[dict[str, str]] = []
    for entry in chain:
        if not isinstance(entry, dict):
            continue
        provider = str(entry.get("provider", "")).strip()
        model = str(entry.get("model", "")).strip()
        if not provider or not model or " " in model or "\n" in model:
            return {
                "ok": False,
                "error": f"invalid fallback entry: provider={provider!r} model={model!r}",
            }
        normalized.append({"provider": provider, "model": model})
    if selection_only:
        user = str(user_id or "").strip()
        if not user:
            return {"ok": False, "error": "unauthorized"}
        user_prefs.write_user_llm_prefs(user, fallback_chain=normalized)
        return {"ok": True, "profile": "", "fallback_chain": normalized, "selection_only": True}
    try:
        target = _agent_model_profile(profile)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if not target:
        return {"ok": False, "error": "no profile resolved"}
    ok, err = _write_fallback_chain(target, normalized)
    if not ok:
        return {"ok": False, "error": err}
    ok, err, synced_runtimes = _sync_agent_model_to_runtimes(
        target,
        current_user_id=str(user_id or "").strip(),
        current_workspace_id=str(workspace_id or "").strip(),
    )
    if not ok:
        return {"ok": False, "error": err}
    _srv()._schedule_gateway_reload(target)
    return {
        "ok": True,
        "profile": target,
        "fallback_chain": normalized,
        "synced_runtimes": synced_runtimes,
    }
