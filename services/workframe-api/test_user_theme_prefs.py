"""Personal appearance preference persists in the authenticated profile."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import zk_auth  # noqa: E402


def test_theme_profile_round_trip_and_legacy_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory(prefix="wf-theme-prefs-") as tmp:
        data_dir = Path(tmp)
        db_path = data_dir / "zk_auth.db"
        data_dir.mkdir(parents=True, exist_ok=True)

        legacy = sqlite3.connect(db_path)
        legacy.executescript(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE profiles (
                user_id TEXT PRIMARY KEY,
                display_name TEXT,
                avatar_url TEXT,
                tagline TEXT,
                bio TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        now = datetime.now(timezone.utc).isoformat()
        legacy.execute("INSERT INTO users VALUES (?, 'active', ?, ?)", ("user-theme", now, now))
        legacy.commit()
        legacy.close()

        monkeypatch.setenv("WORKFRAME_API_DATA_DIR", str(data_dir))
        profile = zk_auth.update_profile("user-theme", {"theme": "blueprint"})

        assert profile is not None
        assert profile["theme"] == "blueprint"
        conn = zk_auth._zk_db()
        try:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(profiles)").fetchall()}
        finally:
            conn.close()
        assert "theme" in columns


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
