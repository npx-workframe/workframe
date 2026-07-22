"""Historical chat badges use completed run evidence, not the current model."""

from __future__ import annotations

import sqlite3

import chat_sessions
import server


def test_session_run_attributions_preserve_model_switch_history(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "workframe.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            session_id TEXT,
            profile_slug TEXT,
            status TEXT,
            created_at TEXT
        );
        CREATE TABLE run_line_items (
            line_item_id TEXT PRIMARY KEY,
            run_id TEXT,
            kind TEXT,
            model TEXT,
            provider TEXT,
            created_at TEXT
        );
        """,
    )
    conn.executemany(
        "INSERT INTO runs VALUES (?,?,?,?,?)",
        [
            ("r1", "session-1", "u-user-agent", "completed", "2026-01-01T00:00:01Z"),
            ("r2", "session-1", "u-user-agent", "completed", "2026-01-01T00:00:02Z"),
        ],
    )
    conn.executemany(
        "INSERT INTO run_line_items VALUES (?,?,?,?,?,?)",
        [
            ("l1", "r1", "llm_turn", "openrouter/auto", "openrouter", "2026-01-01T00:00:01Z"),
            ("l2", "r2", "llm_turn", "google/gemini-2.5-flash", "openrouter", "2026-01-01T00:00:02Z"),
        ],
    )
    conn.commit()
    conn.close()

    def _connect():
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        return db

    monkeypatch.setattr(server, "_workframe_db", _connect)
    assert chat_sessions._session_run_attributions("u-user-agent", "session-1") == [
        ("openrouter/auto", "openrouter"),
        ("google/gemini-2.5-flash", "openrouter"),
    ]
