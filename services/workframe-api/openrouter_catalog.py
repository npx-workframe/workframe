"""Live OpenRouter model list with short TTL cache."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

_CACHE: dict[str, Any] = {"at": 0.0, "rows": []}
_TTL_SEC = int(__import__("os").environ.get("WORKFRAME_OPENROUTER_CATALOG_TTL", "3600"))


def _fetch_models(api_key: str, *, timeout: float = 45) -> list[dict[str, str]]:
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://workfra.me",
            "X-Title": "Workframe",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    rows: list[dict[str, str]] = []
    for item in data.get("data") or []:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("id") or "").strip()
        if not mid:
            continue
        name = str(item.get("name") or mid.rsplit("/", 1)[-1]).strip()
        pricing = item.get("pricing") if isinstance(item.get("pricing"), dict) else {}
        prompt = str(pricing.get("prompt") or "0")
        completion = str(pricing.get("completion") or "0")
        free = prompt in ("0", "0.0") and completion in ("0", "0.0")
        rows.append(
            {
                "provider": "OpenRouter",
                "model": mid,
                "label": name,
                "description": f"{'Free tier · ' if free else ''}{mid}",
            },
        )
    rows.sort(key=lambda r: (0 if ":free" in r["model"] else 1, r["label"].lower()))
    return rows[:120]


def live_suggestions(api_key: str = "", *, limit: int = 40, timeout: float = 45) -> list[dict[str, str]]:
    """Return cached OpenRouter suggestions; empty without a key."""
    key = str(api_key or "").strip()
    if not key:
        return []
    now = time.time()
    if _CACHE["rows"] and now - float(_CACHE["at"]) < _TTL_SEC:
        return list(_CACHE["rows"])[:limit]
    try:
        rows = _fetch_models(key, timeout=timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        return list(_CACHE["rows"])[:limit]
    _CACHE["at"] = now
    _CACHE["rows"] = rows
    return rows[:limit]


def probe_account(api_key: str) -> dict[str, Any]:
    """OpenRouter /key + /credits health for connect-time feedback."""
    key = str(api_key or "").strip()
    if not key:
        return {"ok": False, "error": "missing_key"}
    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "https://workfra.me",
        "X-Title": "Workframe",
    }
    out: dict[str, Any] = {"ok": True, "provider": "openrouter"}
    try:
        with urllib.request.urlopen(
            urllib.request.Request("https://openrouter.ai/api/v1/key", headers=headers, method="GET"),
            timeout=30,
        ) as resp:
            key_data = json.loads(resp.read()).get("data") or {}
        out["key_valid"] = True
        out["label"] = str(key_data.get("label") or "")
        out["usage"] = key_data.get("usage")
    except urllib.error.HTTPError as exc:
        out["ok"] = False
        out["key_valid"] = False
        out["error"] = f"HTTP {exc.code}"
        return out
    except OSError as exc:
        return {"ok": False, "key_valid": False, "error": str(exc)}
    try:
        with urllib.request.urlopen(
            urllib.request.Request("https://openrouter.ai/api/v1/credits", headers=headers, method="GET"),
            timeout=30,
        ) as resp:
            cred = json.loads(resp.read()).get("data") or {}
        total = cred.get("total_credits")
        usage = cred.get("total_usage")
        out["credits_total"] = total
        out["credits_usage"] = usage
        if total is not None and usage is not None:
            out["credits_remaining"] = max(0.0, float(total) - float(usage))
    except (urllib.error.HTTPError, OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return out


if __name__ == "__main__":
    assert live_suggestions("") == []
    print("openrouter_catalog ok (no network without key)")
