"""LLM prefs persist in users.platform_ids without messaging-only validation."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

os.environ.setdefault("WORKFRAME_API_DATA_DIR", str(API_DIR / ".tmp-test-data"))
os.environ.setdefault("HERMES_DATA", str(API_DIR / ".tmp-test-hermes"))
os.environ.setdefault("DEV_LOCAL_UNSAFE", "true")

import server  # noqa: E402


@pytest.fixture()
def llm_prefs_db(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory(prefix="wf-llm-prefs-") as tmp:
        data_dir = Path(tmp) / "api"
        data_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(server, "DATA_DIR", data_dir)
        monkeypatch.setattr(server, "AUTH_DB_PATH", data_dir / "auth.db")
        server._ensure_workframe_db_schema()
        yield data_dir


def _insert_user(*, email: str, display_name: str, platform_ids: str) -> str:
    user_id = str(uuid.uuid4())
    now = str(int(time.time()))
    conn = server._workframe_db()
    try:
        conn.execute(
            "INSERT INTO users (id, email, display_name, role, status, platform_ids, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (user_id, email, display_name, "owner", "active", platform_ids, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return user_id


def test_user_llm_prefs_round_trip(llm_prefs_db) -> None:  # noqa: ARG001
    import user_prefs  # noqa: WPS433

    user_id = _insert_user(email="prefs@test.local", display_name="Prefs", platform_ids="{}")

    user_prefs.write_user_llm_prefs(
        user_id,
        primary="openrouter/google/gemini-2.5-flash",
        fallback_chain=[{"provider": "openrouter", "model": "anthropic/claude-sonnet-4.5"}],
    )

    conn = server._workframe_db()
    try:
        row = conn.execute(
            "SELECT platform_ids FROM users WHERE id = ?", (user_id,),
        ).fetchone()
    finally:
        conn.close()
    pids = json.loads(row["platform_ids"])
    assert pids["llm_primary"] == "openrouter/google/gemini-2.5-flash"
    chain = json.loads(pids["llm_fallback_chain"])
    assert chain[0]["model"] == "anthropic/claude-sonnet-4.5"

    primary, fb = user_prefs.read_user_llm_prefs(user_id)
    assert primary == "openrouter/google/gemini-2.5-flash"
    assert fb[0]["model"] == "anthropic/claude-sonnet-4.5"


def test_user_llm_prefs_infers_primary_from_fallback_chain(llm_prefs_db) -> None:  # noqa: ARG001
    import user_prefs  # noqa: WPS433

    platform_ids = json.dumps({
        "llm_fallback_chain": json.dumps([{"provider": "openrouter", "model": "google/gemini-2.5-flash"}]),
    })
    user_id = _insert_user(
        email="fallback@test.local",
        display_name="Fallback",
        platform_ids=platform_ids,
    )

    inferred, chain = user_prefs.read_user_llm_prefs(user_id)
    assert inferred == "openrouter/google/gemini-2.5-flash"
    assert chain[0]["model"] == "google/gemini-2.5-flash"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
