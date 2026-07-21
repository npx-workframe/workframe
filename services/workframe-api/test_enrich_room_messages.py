"""Regression: _enrich_room_messages must not reference undefined _srv in server.py."""

from __future__ import annotations

import os
import sqlite3
import sys
import uuid
from pathlib import Path

API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

os.environ.setdefault("WORKFRAME_API_DATA_DIR", str(API_DIR / ".tmp-test-data"))
os.environ.setdefault("HERMES_DATA", str(API_DIR / ".tmp-test-hermes"))
os.environ.setdefault("DEV_LOCAL_UNSAFE", "true")

import server  # noqa: E402


def test_enrich_room_messages_preserve_turn_attribution(tmp_path: Path) -> None:
    db = tmp_path / "workframe.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    now = "1700000000"
    agent_id = str(uuid.uuid4())
    room_id = str(uuid.uuid4())
    msg_id = str(uuid.uuid4())
    conn.executescript(
        f"""
        CREATE TABLE agent_profiles (
            id TEXT PRIMARY KEY,
            slug TEXT,
            display_name TEXT,
            model_name TEXT,
            model_provider TEXT,
            deleted_at TEXT
        );
        CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            room_id TEXT,
            sender_user_id TEXT,
            sender_agent_id TEXT,
            parent_message_id TEXT,
            content TEXT,
            content_type TEXT,
            metadata TEXT,
            is_edited INTEGER,
            created_at TEXT,
            updated_at TEXT,
            deleted_at TEXT
        );
        INSERT INTO agent_profiles (id, slug, display_name, model_name, model_provider, deleted_at)
        VALUES ('{agent_id}', 'test-agent', 'Test Agent', 'gpt-4o-mini', 'openai', NULL);
        INSERT INTO messages (
            id, room_id, sender_user_id, sender_agent_id, parent_message_id,
            content, content_type, metadata, is_edited, created_at, updated_at, deleted_at
        ) VALUES (
            '{msg_id}', '{room_id}', NULL, '{agent_id}', NULL,
            'Hello!', 'text', '{{"model":"google/gemini-2.5-flash","llm_provider":"openrouter"}}',
            0, '{now}', '{now}', NULL
        );
        """
    )
    rows = conn.execute("SELECT * FROM messages").fetchall()
    enriched = server._enrich_room_messages(conn, rows)
    conn.close()

    assert len(enriched) == 1
    assert enriched[0]["content"] == "Hello!"
    assert enriched[0]["sender_agent_slug"] == "test-agent"
    assert enriched[0]["sender_agent_name"] == "Test Agent"
    assert enriched[0]["model"] == "google/gemini-2.5-flash"
    assert enriched[0]["llm_provider"] == "openrouter"


def test_enrich_room_messages_does_not_relabel_legacy_message(tmp_path: Path) -> None:
    db = tmp_path / "workframe.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE agent_profiles (
            id TEXT PRIMARY KEY, slug TEXT, display_name TEXT,
            model_name TEXT, model_provider TEXT, deleted_at TEXT
        );
        CREATE TABLE messages (
            id TEXT PRIMARY KEY, room_id TEXT, sender_user_id TEXT,
            sender_agent_id TEXT, parent_message_id TEXT, content TEXT,
            content_type TEXT, metadata TEXT, is_edited INTEGER,
            created_at TEXT, updated_at TEXT, deleted_at TEXT
        );
        INSERT INTO agent_profiles VALUES (
            'agent-1', 'test-agent', 'Test Agent',
            'gpt-5.4-mini', 'codex', NULL
        );
        INSERT INTO messages VALUES (
            'message-1', 'room-1', NULL, 'agent-1', NULL, 'Old reply',
            'text', '{}', 0, '1700000000', '1700000000', NULL
        );
        """
    )

    enriched = server._enrich_room_messages(
        conn,
        conn.execute("SELECT * FROM messages").fetchall(),
    )
    conn.close()

    assert enriched[0]["sender_agent_name"] == "Test Agent"
    assert "model" not in enriched[0]
    assert "llm_provider" not in enriched[0]
