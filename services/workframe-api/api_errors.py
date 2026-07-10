"""Public API error codes and sanitization — never leak tracebacks to clients."""
from __future__ import annotations

import re
from typing import Any

_TRACE = re.compile(r"\n(?:Traceback|  File )", re.MULTILINE)
_SNAKE_CODE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")

PUBLIC: dict[str, dict[str, str]] = {
    "request_failed": {
        "message": "Something went wrong.",
        "hint": "Try again in a moment. If it keeps happening, contact your admin.",
    },
    "runtime_profile_permission_denied": {
        "message": "Workframe could not prepare your agent workspace on disk.",
        "hint": "An admin should restart the stack or fix permissions on the Agents data volume.",
    },
    "runtime_profile_create_failed": {
        "message": "Workframe could not create your personal agent profile.",
        "hint": "Try again in a moment. If it persists, restart Workframe or contact your admin.",
    },
    "runtime_profile_api_config_failed": {
        "message": "Workframe could not start the agent API for this profile.",
        "hint": "Check that the Hermes gateway is running and try again.",
    },
    "runtime_profile_bootstrap_failed": {
        "message": "Workframe could not finish setting up this agent profile.",
        "hint": "Try again or pick another agent from the crew list.",
    },
    "session_bootstrap_failed": {
        "message": "Workframe could not start this chat session.",
        "hint": "Refresh the page or open another agent room.",
    },
    "room_not_found": {
        "message": "That chat room was not found.",
        "hint": "Refresh the room list or open another chat.",
    },
    "room_access_denied": {
        "message": "You cannot access this room.",
        "hint": "Ask a workspace admin for access.",
    },
    "no_session": {
        "message": "You are not signed in.",
        "hint": "Refresh the page and sign in again.",
    },
}


def scrub_internal(text: str) -> str:
    """Drop tracebacks and multiline internals — keep a single safe line for logs."""
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    if _TRACE.search(cleaned):
        cleaned = _TRACE.split(cleaned, maxsplit=1)[0].strip()
    if "\n" in cleaned:
        cleaned = cleaned.split("\n", 1)[0].strip()
    return cleaned


def classify_error(text: str) -> str | None:
    raw_full = str(text or "")
    lowered_full = raw_full.lower()
    if "permissionerror" in lowered_full or "permission denied" in lowered_full:
        return "runtime_profile_permission_denied"
    raw = scrub_internal(text)
    if not raw:
        return None
    lowered = raw.lower()
    if "runtime profile create failed" in lowered:
        return "runtime_profile_create_failed"
    if "runtime profile api config failed" in lowered:
        return "runtime_profile_api_config_failed"
    if "runtime profile bootstrap failed" in lowered:
        return "runtime_profile_bootstrap_failed"
    if "connection refused" in lowered_full or "errno 111" in lowered_full:
        return "runtime_profile_api_config_failed"
    if "profile api did not become healthy" in lowered or "profile api unavailable" in lowered:
        return "runtime_profile_api_config_failed"
    if "session creation failed" in lowered or "create session failed" in lowered:
        return "session_bootstrap_failed"
    if "room_not_found" in lowered or "room not found" in lowered:
        return "room_not_found"
    if "room_access_denied" in lowered or "access denied" in lowered:
        return "room_access_denied"
    if "no_session" in lowered:
        return "no_session"
    if _SNAKE_CODE.fullmatch(raw):
        return raw
    return None


def public_api_error_payload(exc: BaseException, *, context: str = "") -> dict[str, Any]:
    """Map an exception to a client-safe {error, message, hint} payload."""
    full = str(exc)
    code = classify_error(full)
    if code and code in PUBLIC:
        row = PUBLIC[code]
        return {"error": code, "message": row["message"], "hint": row.get("hint", "")}
    if code and _SNAKE_CODE.fullmatch(code):
        human = code.replace("_", " ").strip().capitalize() + "."
        return {"error": code, "message": human, "hint": PUBLIC["request_failed"]["hint"]}
    fallback = PUBLIC["request_failed"]
    payload: dict[str, Any] = {
        "error": "request_failed",
        "message": fallback["message"],
        "hint": fallback["hint"],
    }
    if context.strip():
        payload["context"] = context.strip()
    return payload


def http_status_for_code(code: str) -> int:
    if code in ("no_session",):
        return 401
    if code in ("room_access_denied", "forbidden"):
        return 403
    if code in ("room_not_found",):
        return 404
    return 400
