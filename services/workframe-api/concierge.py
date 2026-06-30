"""Deterministic concierge when LLM is unavailable — keyword intent router, no LLM."""

from __future__ import annotations

import re
from typing import Any

import llm_error_glossary as glossary

# ponytail: (intent_id, patterns) — first match wins
_INTENTS: list[tuple[str, tuple[str, ...]]] = [
    (
        "add_provider_keys",
        (
            "add key",
            "add keys",
            "api key",
            "connect openrouter",
            "connect provider",
            "where key",
            "how do i connect",
            "how to connect",
            "openrouter key",
            "llm key",
            "provider key",
        ),
    ),
    (
        "change_model",
        (
            "set model",
            "change model",
            "pick model",
            "which model",
            "how do i set model",
            "how to set model",
            "choose model",
            "switch model",
            "model picker",
        ),
    ),
    (
        "provider_credits",
        (
            "out of credit",
            "no credit",
            "add credit",
            "billing",
            "top up",
            "purchase credit",
        ),
    ),
    (
        "invalid_key",
        (
            "invalid key",
            "key rejected",
            "bad key",
            "wrong key",
            "401",
            "unauthorized",
        ),
    ),
    (
        "diagnose",
        (
            "what's wrong",
            "whats wrong",
            "why no reply",
            "not working",
            "not replying",
            "help me",
            "what happened",
        ),
    ),
    (
        "getting_started",
        (
            "get started",
            "how do i start",
            "how to start",
            "new here",
            "first time",
        ),
    ),
]

_INTENT_PLAYBOOK: dict[str, dict[str, Any]] = {
    "add_provider_keys": {
        "message": "Connect an LLM provider to enable chat.",
        "hint": "OpenRouter is the fastest path — paste your API key under Connected accounts.",
        "action": {"type": "open_settings", "tab": "providers"},
        "action_label": "Add API key",
        "code": "concierge_add_keys",
    },
    "change_model": {
        "message": "Choose which model this agent uses.",
        "hint": "Open the model picker and select a model your provider supports.",
        "action": {"type": "open_settings", "tab": "model"},
        "action_label": "Choose model",
        "code": "concierge_change_model",
    },
    "provider_credits": glossary.playbook_entry("provider_no_credits"),
    "invalid_key": glossary.playbook_entry("provider_invalid_key"),
    "diagnose": {
        "message": "I can help you troubleshoot setup.",
        "hint": "Connect a provider first, then pick a live model. If chat still fails, check credits and the model name.",
        "action": {"type": "open_settings", "tab": "providers"},
        "action_label": "Connected accounts",
        "secondary_action": {"type": "open_settings", "tab": "model"},
        "secondary_action_label": "Choose model",
        "code": "concierge_diagnose",
    },
    "getting_started": {
        "message": "Welcome to Workframe. Three steps to your first agent reply:",
        "hint": "1) Connect an LLM provider · 2) Pick a model · 3) Send a message in chat.",
        "action": {"type": "open_settings", "tab": "providers"},
        "action_label": "Connect provider",
        "code": "concierge_getting_started",
    },
    "fallback_help": glossary.playbook_entry("no_llm_provider"),
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower().strip())


def match_intent(user_text: str) -> str:
    norm = _normalize(user_text)
    if not norm:
        return "fallback_help"
    for intent_id, patterns in _INTENTS:
        for pat in patterns:
            if pat in norm:
                return intent_id
    return "fallback_help"


def respond(
    user_text: str,
    *,
    situation: str = "",
    last_error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return concierge playbook for user message or classified error."""
    if last_error and str(last_error.get("code") or "") not in ("", "concierge"):
        entry = dict(last_error)
        entry.setdefault("message", entry.get("text") or "")
        hint = str(entry.get("hint") or "").strip()
        if hint:
            entry["hint"] = f"{hint} You can also ask how to connect keys or change models."
        return glossary.notice_payload(entry)

    if situation == "no_provider":
        intent = match_intent(user_text)
        if intent == "fallback_help":
            return glossary.notice_payload(_INTENT_PLAYBOOK["getting_started"])
        return glossary.notice_payload(_INTENT_PLAYBOOK.get(intent) or _INTENT_PLAYBOOK["fallback_help"])

    intent = match_intent(user_text)
    row = dict(_INTENT_PLAYBOOK.get(intent) or _INTENT_PLAYBOOK["fallback_help"])
    return glossary.notice_payload(row)


if __name__ == "__main__":
    r = respond("how do I add keys?", situation="no_provider")
    assert r["code"] == "concierge_add_keys"
    r2 = respond("how do I set model?", situation="no_provider")
    assert r2["code"] == "concierge_change_model"
    r3 = respond("hello", situation="no_provider")
    assert r3["code"] == "concierge_getting_started"
    print("concierge ok")
