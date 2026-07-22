from __future__ import annotations

import sqlite3

import pytest

import db_schema
import message_reactions


def reaction_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, description TEXT, applied_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE messages (id TEXT PRIMARY KEY, room_id TEXT, deleted_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE users (id TEXT PRIMARY KEY, display_name TEXT, avatar_url TEXT)"
    )
    # Run-ledger already owns migration 14. This regression marker ensures
    # reactions still migrate on installs that have that older row.
    conn.execute(
        "INSERT INTO schema_migrations VALUES ('14', 'runs, run_events, run_line_items ledger tables', 'now')"
    )
    db_schema._migrate_v15_message_reactions(conn)
    assert conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version = '15'"
    ).fetchone()
    conn.execute("INSERT INTO messages (id, room_id, deleted_at) VALUES ('message-1', 'room-1', NULL)")
    conn.executemany(
        "INSERT INTO users (id, display_name, avatar_url) VALUES (?, ?, ?)",
        [
            ("user-1", "Alan", "/avatars/alan.png"),
            ("user-2", "Grace", None),
        ],
    )
    conn.commit()
    return conn


def can_access_room(_conn: sqlite3.Connection, room_id: str, user_id: str) -> bool:
    return room_id == "room-1" and user_id == "user-1"


def test_room_reaction_toggles_and_aggregates() -> None:
    conn = reaction_db()
    try:
        first = message_reactions.toggle_reaction(
            conn, "room:room-1", "message-1", "👍", "user-1", can_access_room
        )
        assert first["reacted"] is True
        assert first["reactions"] == [
            {
                "message_id": "message-1",
                "emoji": "👍",
                "count": 1,
                "reacted": True,
                "reactors": [
                    {
                        "user_id": "user-1",
                        "display_name": "Alan",
                        "avatar_url": "/avatars/alan.png",
                    }
                ],
            }
        ]

        second = message_reactions.toggle_reaction(
            conn, "room:room-1", "message-1", "👍", "user-1", can_access_room
        )
        assert second["reacted"] is False
        assert second["reactions"] == []
    finally:
        conn.close()


def test_room_reactions_include_people_for_hover_details() -> None:
    conn = reaction_db()
    try:
        message_reactions.toggle_reaction(
            conn, "room:room-1", "message-1", "🎉", "user-1", can_access_room
        )
        conn.execute(
            """
            INSERT INTO message_reactions (scope_key, message_id, user_id, emoji, created_at)
            VALUES ('room:room-1', 'message-1', 'user-2', '🎉', '2')
            """
        )
        conn.commit()

        listed = message_reactions.list_reactions(
            conn, "room:room-1", "user-1", can_access_room
        )
        assert listed["reactions"] == [
            {
                "message_id": "message-1",
                "emoji": "🎉",
                "count": 2,
                "reacted": True,
                "reactors": [
                    {
                        "user_id": "user-1",
                        "display_name": "Alan",
                        "avatar_url": "/avatars/alan.png",
                    },
                    {
                        "user_id": "user-2",
                        "display_name": "Grace",
                        "avatar_url": None,
                    },
                ],
            }
        ]
    finally:
        conn.close()


def test_room_reactions_require_room_access_and_existing_message() -> None:
    conn = reaction_db()
    try:
        with pytest.raises(PermissionError):
            message_reactions.list_reactions(
                conn, "room:room-1", "user-2", can_access_room
            )
        with pytest.raises(ValueError, match="message_not_found"):
            message_reactions.toggle_reaction(
                conn, "room:room-1", "missing", "🔥", "user-1", can_access_room
            )
    finally:
        conn.close()


def test_dm_reactions_are_namespaced_by_authenticated_user() -> None:
    conn = reaction_db()
    try:
        message_reactions.toggle_reaction(
            conn, "dm:agent:session-1", "external-message", "✅", "user-1", can_access_room
        )
        mine = message_reactions.list_reactions(
            conn, "dm:agent:session-1", "user-1", can_access_room
        )
        theirs = message_reactions.list_reactions(
            conn, "dm:agent:session-1", "user-2", can_access_room
        )
        assert mine["reactions"][0]["count"] == 1
        assert theirs["reactions"] == []
    finally:
        conn.close()
