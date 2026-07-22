"""Account-scoped live model discovery for Workframe's LLM providers."""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_TTL_SEC = int(os.environ.get("WORKFRAME_MODEL_CATALOG_TTL", "900"))
_ERROR_TTL_SEC = int(os.environ.get("WORKFRAME_MODEL_CATALOG_ERROR_TTL", "30"))
_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def _request_json(url: str, *, headers: dict[str, str] | None = None, timeout: float = 8) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read())
    return payload if isinstance(payload, dict) else {}


def _row(provider: str, model: str, label: str = "", description: str = "") -> dict[str, str]:
    model_id = str(model or "").strip()
    return {
        "provider": provider,
        "billing_provider": provider,
        "model": model_id,
        "label": str(label or model_id).strip() or model_id,
        "description": str(description or model_id).strip() or model_id,
        "catalog_source": "live",
    }


def _openrouter_models(api_key: str, timeout: float) -> list[dict[str, str]]:
    payload = _request_json(
        "https://openrouter.ai/api/v1/models?output_modalities=text",
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://workfra.me",
            "X-Title": "Workframe",
        },
        timeout=timeout,
    )
    rows: list[dict[str, str]] = []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue
        name = str(item.get("name") or model_id.rsplit("/", 1)[-1]).strip()
        rows.append(_row("openrouter", model_id, name, model_id))
    return sorted(rows, key=lambda item: item["label"].lower())


def _openai_models(api_key: str, timeout: float) -> list[dict[str, str]]:
    payload = _request_json(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    excluded = ("audio", "embedding", "image", "moderation", "realtime", "search", "transcribe", "tts", "whisper")
    rows: list[dict[str, str]] = []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        lower = model_id.lower()
        if not model_id or any(token in lower for token in excluded):
            continue
        if not lower.startswith(("gpt-", "chatgpt-", "o1", "o3", "o4")):
            continue
        rows.append(_row("openai", model_id))
    return sorted(rows, key=lambda item: item["model"].lower())


def _anthropic_models(api_key: str, timeout: float) -> list[dict[str, str]]:
    payload = _request_json(
        "https://api.anthropic.com/v1/models?limit=1000",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        timeout=timeout,
    )
    rows: list[dict[str, str]] = []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if model_id:
            rows.append(_row("anthropic", model_id, str(item.get("display_name") or model_id)))
    return rows


def _google_models(api_key: str, timeout: float) -> list[dict[str, str]]:
    query = urllib.parse.urlencode({"key": api_key, "pageSize": "1000"})
    payload = _request_json(f"https://generativelanguage.googleapis.com/v1beta/models?{query}", timeout=timeout)
    rows: list[dict[str, str]] = []
    for item in payload.get("models") or []:
        if not isinstance(item, dict) or "generateContent" not in (item.get("supportedGenerationMethods") or []):
            continue
        model_id = str(item.get("name") or "").removeprefix("models/").strip()
        if model_id:
            rows.append(_row(
                "google", model_id, str(item.get("displayName") or model_id),
                str(item.get("description") or model_id),
            ))
    return rows


def _deepseek_models(api_key: str, timeout: float) -> list[dict[str, str]]:
    payload = _request_json(
        "https://api.deepseek.com/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    return [
        _row("deepseek", str(item.get("id") or ""))
        for item in payload.get("data") or []
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    ]


def _codex_models(access_token: str, timeout: float) -> list[dict[str, str]]:
    payload = _request_json(
        "https://chatgpt.com/backend-api/codex/models?client_version=1.0.0",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=timeout,
    )
    sortable: list[tuple[int, dict[str, str]]] = []
    for item in payload.get("models") or []:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("slug") or "").strip()
        visibility = str(item.get("visibility") or "").strip().lower()
        if not model_id or visibility in {"hide", "hidden"}:
            continue
        priority = item.get("priority")
        rank = int(priority) if isinstance(priority, (int, float)) else 10_000
        display = str(item.get("display_name") or item.get("displayName") or model_id).strip()
        sortable.append((rank, _row("codex", model_id, display)))
    sortable.sort(key=lambda item: (item[0], item[1]["model"]))
    return [item[1] for item in sortable]


_FETCHERS = {
    "openrouter": _openrouter_models,
    "openai": _openai_models,
    "anthropic": _anthropic_models,
    "google": _google_models,
    "deepseek": _deepseek_models,
    "codex": _codex_models,
}


def _cache_key(provider: str, credential: str) -> tuple[str, str]:
    digest = hashlib.sha256(credential.encode("utf-8")).hexdigest()[:20] if credential else ""
    return provider, digest


def discover(provider: str, credential: str, *, timeout: float = 8) -> tuple[list[dict[str, str]], dict[str, str]]:
    provider_id = str(provider or "").strip().lower()
    secret = str(credential or "").strip()
    if provider_id not in _FETCHERS:
        return [], {"status": "unsupported", "message": "Use a custom model id for this provider."}
    if not secret:
        return [], {"status": "unauthenticated", "message": "Reconnect this provider to refresh its models."}
    key = _cache_key(provider_id, secret)
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached:
        ttl = _TTL_SEC if cached.get("status") == "live" else _ERROR_TTL_SEC
        if now - float(cached.get("at") or 0) < ttl:
            return list(cached.get("rows") or []), dict(cached.get("meta") or {})
    try:
        rows = _FETCHERS[provider_id](secret, timeout)
        meta = {
            "status": "live" if rows else "empty",
            "message": f"{len(rows)} models available now." if rows else "The provider returned no chat models.",
        }
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, OSError, ValueError):
        rows = []
        meta = {"status": "error", "message": "Live catalog unavailable. Retry or enter a custom model id."}
    _CACHE[key] = {"at": now, "status": meta["status"], "rows": rows, "meta": meta}
    return list(rows), dict(meta)


def discover_many(credentials: dict[str, str], *, timeout: float = 8) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    rows: list[dict[str, str]] = []
    statuses: dict[str, dict[str, str]] = {}
    if not credentials:
        return rows, statuses
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(credentials))) as pool:
        pending = {
            pool.submit(discover, provider, credential, timeout=timeout): provider
            for provider, credential in credentials.items()
        }
        for future in concurrent.futures.as_completed(pending):
            provider = pending[future]
            try:
                provider_rows, meta = future.result()
            except Exception:
                provider_rows, meta = [], {
                    "status": "error",
                    "message": "Live catalog unavailable. Retry or enter a custom model id.",
                }
            rows.extend(provider_rows)
            statuses[provider] = meta
    return rows, statuses


def oauth_access_token(auth: dict[str, Any] | None, hermes_auth_id: str) -> str:
    """Read an OAuth access token from Hermes provider or credential-pool layouts."""
    if not isinstance(auth, dict):
        return ""
    raw = str(hermes_auth_id or "").strip().lower()
    keys = {raw, raw.replace("-", ""), raw.replace("-", "_")}
    if "-" in raw:
        keys.add(raw.split("-")[-1])

    def token_from(entry: Any) -> str:
        if not isinstance(entry, dict):
            return ""
        tokens = entry.get("tokens") if isinstance(entry.get("tokens"), dict) else {}
        for source in (tokens, entry):
            for field in ("access_token", "accessToken", "token"):
                value = str(source.get(field) or "").strip()
                if value:
                    return value
        return ""

    providers = auth.get("providers")
    if isinstance(providers, dict):
        for key, entry in providers.items():
            if str(key).lower() in keys:
                token = token_from(entry)
                if token:
                    return token
    credentials = auth.get("credentials")
    if isinstance(credentials, list):
        for entry in credentials:
            if not isinstance(entry, dict):
                continue
            provider = str(entry.get("provider") or entry.get("id") or "").lower()
            if provider in keys:
                token = token_from(entry)
                if token:
                    return token
    pool = auth.get("credential_pool")
    if isinstance(pool, dict):
        for key, entries in pool.items():
            if str(key).lower() not in keys or not isinstance(entries, list):
                continue
            for entry in entries:
                token = token_from(entry)
                if token:
                    return token
    return ""
