"""WF-032 chat_bind self-check."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chat_bind  # noqa: E402


def test_extract_title() -> None:
    assert chat_bind._extract_title("# Hello World\nbody", "fallback") == "Hello World"
    assert chat_bind._extract_title("no heading", "fallback") == "fallback"
    assert chat_bind._extract_title("  # Indented\n", "x") == "Indented"


def test_enrich_room_chat_payload_sets_user() -> None:
    out = chat_bind._enrich_room_chat_payload({"text": "hi"}, "user-1")
    assert out["user_id"] == "user-1"
    assert out["text"] == "hi"


def test_room_chat_bind_delegates_room_id() -> None:
    """room_chat_bind injects room_id then calls profile_chat_bind."""
    calls: list[tuple] = []

    orig = chat_bind.profile_chat_bind
    chat_bind.profile_chat_bind = lambda profile, payload, user_id="": (
        calls.append((profile, payload, user_id)) or {"ok": True, "session_id": "s1"}
    )
    try:
        chat_bind.room_chat_bind("room-abc", {"source_id": "ui"}, "u1")
    finally:
        chat_bind.profile_chat_bind = orig

    assert len(calls) == 1
    assert calls[0][0] == ""
    assert calls[0][1]["room_id"] == "room-abc"
    assert calls[0][2] == "u1"


if __name__ == "__main__":
    test_extract_title()
    test_enrich_room_chat_payload_sets_user()
    test_room_chat_bind_delegates_room_id()
    print("test_chat_bind: ok")
