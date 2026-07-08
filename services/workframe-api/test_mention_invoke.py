"""WF-032 mention_invoke self-check."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mention_invoke  # noqa: E402


def test_invoke_mention_missing_agent() -> None:
    """No-op when agent row lacks slug/id."""
    mention_invoke._invoke_room_agent_mention(
        "room-1",
        "ws-1",
        {"slug": "", "id": ""},
        "",
        "msg-1",
    )


if __name__ == "__main__":
    test_invoke_mention_missing_agent()
    print("test_mention_invoke: ok")
