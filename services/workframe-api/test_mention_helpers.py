"""WF-032 mention_helpers self-check."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mention_helpers  # noqa: E402


def test_mention_handle() -> None:
    assert mention_helpers.mention_handle("Alice Smith") == "alicesmith"
    assert mention_helpers.mention_handle("", "alice@example.com") == "alice"


def test_parse_room_mentions() -> None:
    agents = [{"id": "a1", "slug": "dev", "display_name": "Dev Agent"}]
    result = mention_helpers.parse_room_mentions("@dev please review", agents, [])
    assert len(result["agents"]) == 1
    assert result["agents"][0]["slug"] == "dev"
    assert result["users"] == []


def test_parse_mentions() -> None:
    rows = mention_helpers.parse_mentions("hello @architect and @dev")
    assert [r["slug"] for r in rows] == ["architect", "dev"]


if __name__ == "__main__":
    test_mention_handle()
    test_parse_room_mentions()
    test_parse_mentions()
    print("test_mention_helpers: ok")
