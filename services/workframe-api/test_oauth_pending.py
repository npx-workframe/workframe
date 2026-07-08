"""WF-032 oauth_pending store/take self-check."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import oauth_pending  # noqa: E402
import server  # noqa: E402


def test_store_take_round_trip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["WORKFRAME_API_DATA_DIR"] = tmp
        server.DATA_DIR = Path(tmp)
        server.AUTH_DB_PATH = Path(tmp) / "auth.db"
        server._ensure_workframe_db_schema()
        oauth_pending.store_pending("state-1", "user-1", "github", "verifier-abc", "ws-1")
        row = oauth_pending.take_pending("state-1")
        assert row is not None
        assert row["user_id"] == "user-1"
        assert row["provider"] == "github"
        assert row["code_verifier"] == "verifier-abc"
        assert oauth_pending.take_pending("state-1") is None


def test_pkce_pair() -> None:
    verifier, challenge = oauth_pending.pkce_pair()
    assert len(verifier) > 20
    assert len(challenge) > 20
    assert verifier != challenge


if __name__ == "__main__":
    test_pkce_pair()
    test_store_take_round_trip()
    print("test_oauth_pending: ok")
