"""Classify LLM/provider failures into didactic copy + UI actions."""

from __future__ import annotations

import json
import re
from typing import Any

# ponytail: static playbook — extend rows, no LLM generation
_ACTIONS: dict[str, dict[str, Any]] = {
    "open_providers": {"type": "open_settings", "tab": "providers"},
    "open_model": {"type": "open_settings", "tab": "model"},
    "retry": {"type": "retry"},
    "openrouter_credits": {
        "type": "external_link",
        "url": "https://openrouter.ai/credits",
        "label": "Add credits",
    },
    "openrouter_keys": {
        "type": "external_link",
        "url": "https://openrouter.ai/keys",
        "label": "Manage keys",
    },
}

PLAYBOOK: dict[str, dict[str, Any]] = {
    "no_llm_provider": {
        "message": "No model provider is connected for your account yet.",
        "hint": "Connect OpenRouter or another LLM provider under Connected accounts, then try again.",
        "action": _ACTIONS["open_providers"],
        "action_label": "Connect provider",
    },
    "provider_invalid_key": {
        "message": "Your API key was rejected by the provider.",
        "hint": "The key may be expired or revoked. Paste a new one under Settings → Integrations.",
        "action": _ACTIONS["open_providers"],
        "action_label": "Update API key",
        "secondary_action": _ACTIONS["openrouter_keys"],
        "secondary_action_label": "Open provider keys",
    },
    "provider_no_credits": {
        "message": "Your provider account has no credits remaining.",
        "hint": "Add credits at your provider billing page, then send your message again.",
        "action": _ACTIONS["openrouter_credits"],
        "action_label": "Add credits",
        "secondary_action": _ACTIONS["open_model"],
        "secondary_action_label": "Choose another model",
    },
    "model_unavailable": {
        "message": "The selected model is not available on your provider right now.",
        "hint": "Pick a different model in Settings. Free models on OpenRouter rotate often.",
        "action": _ACTIONS["open_model"],
        "action_label": "Choose model",
    },
    "model_invalid_id": {
        "message": "That model ID is not valid for your provider.",
        "hint": "Open the model picker and select a model from the list, or type a known provider/model id.",
        "action": _ACTIONS["open_model"],
        "action_label": "Choose model",
    },
    "provider_rate_limited": {
        "message": "The provider rate-limited this request.",
        "hint": "Wait a minute or switch to another model.",
        "action": _ACTIONS["open_model"],
        "action_label": "Choose model",
    },
    "invalid_lease": {
        "message": "Your session credential expired before the model replied.",
        "hint": "Send the message again — Workframe will issue a fresh credential.",
        "action": _ACTIONS["retry"],
        "action_label": "Try again",
    },
    "provider_empty_reply": {
        "message": "The model provider returned no reply.",
        "hint": "Check your API key, credits, and model selection in Settings.",
        "action": _ACTIONS["open_model"],
        "action_label": "Check model",
        "secondary_action": _ACTIONS["open_providers"],
        "secondary_action_label": "Check API key",
    },
    "provider_gateway_error": {
        "message": "Workframe could not reach the model gateway.",
        "hint": "Confirm the stack is running and try again.",
        "action": _ACTIONS["retry"],
        "action_label": "Try again",
    },
    "unknown_provider_error": {
        "message": "The model request failed.",
        "hint": "Check Connected accounts and the model in Settings.",
        "action": _ACTIONS["open_providers"],
        "action_label": "Connected accounts",
        "secondary_action": _ACTIONS["open_model"],
        "secondary_action_label": "Choose model",
    },
}


_PROVIDER_LABELS: dict[str, str] = {
    "openrouter": "OpenRouter",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "deepseek": "DeepSeek",
}


def _provider_label(provider: str) -> str:
    key = str(provider or "openrouter").strip().lower()
    return _PROVIDER_LABELS.get(key, key.title() or "Provider")


def tailor_provider_entry(entry: dict[str, Any], provider: str) -> dict[str, Any]:
    """Agent-facing copy when a provider rejects credentials."""
    if str(entry.get("code") or "") != "provider_invalid_key":
        return entry
    label = _provider_label(provider)
    out = dict(entry)
    out["message"] = (
        f"I couldn't authenticate with {label} — your API key may be expired or revoked."
    )
    out["hint"] = (
        f"Open Settings → Integrations to paste a new {label} key, then send your message again."
    )
    if str(provider or "").strip().lower() == "openrouter":
        out["secondary_action"] = _ACTIONS["openrouter_keys"]
        out["secondary_action_label"] = "Manage OpenRouter keys"
    return out


def playbook_entry(code: str, **overrides: Any) -> dict[str, Any]:
    """Return a copy of a playbook row with optional string format overrides."""
    base = dict(PLAYBOOK.get(code) or PLAYBOOK["unknown_provider_error"])
    base["code"] = code
    for key, value in overrides.items():
        if value is not None and key in base and isinstance(base[key], str):
            try:
                base[key] = base[key].format(**overrides)
            except (KeyError, ValueError):
                base[key] = str(value)
        elif value is not None:
            base[key] = value
    return base


def _parse_json_blob(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text or text[0] not in "{[":
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _extract_error_message(data: dict[str, Any] | None, raw: str = "") -> str:
    if data:
        err = data.get("error")
        if isinstance(err, dict):
            msg = str(err.get("message") or "").strip()
            if msg:
                return msg
        if isinstance(err, str) and err.strip():
            return err.strip()
        for key in ("message", "detail"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return str(raw or "").strip()


def _model_from_text(text: str) -> str:
    m = re.search(r"for\s+([a-z0-9_.:/-]+)", text, re.I)
    return m.group(1) if m else ""


def classify_upstream(
    status: int,
    body: bytes | str | None = None,
    *,
    provider: str = "openrouter",
    model: str = "",
) -> dict[str, Any]:
    """Map upstream HTTP status + body to playbook entry."""
    raw = body.decode("utf-8", errors="replace") if isinstance(body, (bytes, bytearray)) else str(body or "")
    data = _parse_json_blob(raw)
    msg = _extract_error_message(data, raw)
    low = msg.lower()
    model_id = model or _model_from_text(msg)

    if (
        status == 401
        or "invalid api key" in low
        or "incorrect api key" in low
        or "unauthorized" in low
        or "user not found" in low
    ):
        return tailor_provider_entry(
            playbook_entry("provider_invalid_key", provider=provider),
            provider,
        )
    if status == 402 or "insufficient" in low and "credit" in low or "payment required" in low:
        return playbook_entry("provider_no_credits", provider=provider)
    if status == 429 or "rate limit" in low:
        return playbook_entry("provider_rate_limited", provider=provider)
    if status == 400 and ("not a valid model" in low or "invalid model" in low):
        entry = playbook_entry("model_invalid_id", model=model_id or "selected model")
        if model_id:
            entry["message"] = f"Model `{model_id}` is not a valid id on {provider}."
        return entry
    if status == 404 or "no endpoints found" in low or "model not found" in low:
        entry = playbook_entry("model_unavailable", model=model_id or "selected model")
        if model_id:
            entry["message"] = f"Model `{model_id}` has no live endpoints on {provider} right now."
        return entry
    if status >= 500:
        return playbook_entry("provider_gateway_error", provider=provider)
    return playbook_entry("unknown_provider_error", provider=provider, detail=msg[:200] if msg else "")


def classify_exception_text(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return playbook_entry("provider_empty_reply")
    if "no_llm_provider_for_user" in raw:
        return playbook_entry("no_llm_provider")
    if "invalid_lease" in raw or "credential expired" in raw.lower():
        return playbook_entry("invalid_lease")
    m = re.search(r"HTTP (\d{3})", raw)
    if m:
        return classify_upstream(int(m.group(1)), raw)
    low = raw.lower()
    if "no endpoints found" in low or "model" in low and "not found" in low:
        return classify_upstream(404, raw)
    if "not a valid model" in low:
        return classify_upstream(400, raw)
    if "rate limit" in low:
        return classify_upstream(429, raw)
    if "credit" in low:
        return classify_upstream(402, raw)
    if "api key" in low or "unauthorized" in low or "user not found" in low:
        return classify_upstream(401, raw)
    return playbook_entry("unknown_provider_error", detail=raw[:200])


def classify_stream_error(text: str, *, provider: str = "openrouter") -> dict[str, Any]:
    """Classify upstream/Hermes failure text into UI notice payload."""
    entry = classify_exception_text(str(text or "").strip())
    entry = tailor_provider_entry(entry, provider)
    return notice_payload(entry)


def notice_payload(entry: dict[str, Any]) -> dict[str, Any]:
    """SSE/JSON-safe dict for UI."""
    out: dict[str, Any] = {
        "code": str(entry.get("code") or "unknown_provider_error"),
        "message": str(entry.get("message") or ""),
        "hint": str(entry.get("hint") or ""),
        "text": str(entry.get("message") or ""),
        "error": str(entry.get("message") or ""),
    }
    action = entry.get("action")
    if isinstance(action, dict):
        out["action"] = action
    label = entry.get("action_label")
    if label:
        out["action_label"] = str(label)
    sec = entry.get("secondary_action")
    if isinstance(sec, dict):
        out["secondary_action"] = sec
    sec_label = entry.get("secondary_action_label")
    if sec_label:
        out["secondary_action_label"] = str(sec_label)
    return out


if __name__ == "__main__":
    e = classify_upstream(404, b'{"error":{"message":"No endpoints found for openrouter/owl-alpha."}}', model="openrouter/owl-alpha")
    assert e["code"] == "model_unavailable"
    e2 = classify_exception_text("no_llm_provider_for_user: Connect an LLM provider")
    assert e2["code"] == "no_llm_provider"
    e3 = classify_upstream(401, b'{"error":"Invalid API key"}')
    assert e3["code"] == "provider_invalid_key"
    e4 = classify_exception_text("HTTP 401: User not found.")
    assert e4["code"] == "provider_invalid_key"
    assert "OpenRouter" in e4["message"] or "authenticate" in e4["message"]
    p = classify_stream_error("HTTP 401: User not found.", provider="openrouter")
    assert p["code"] == "provider_invalid_key"
    assert p.get("action", {}).get("type") == "open_settings"
    print("llm_error_glossary ok")
