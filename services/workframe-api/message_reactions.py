"""Authenticated message reactions shared by room and agent-DM chat surfaces."""
from __future__ import annotations

import sqlite3
import time
from typing import Any, Callable


RoomAccessCheck = Callable[[sqlite3.Connection, str, str], bool]


def _resolved_scope(
    conn: sqlite3.Connection,
    scope: str,
    user_id: str,
    can_access_room: RoomAccessCheck,
) -> tuple[str, str | None]:
    raw = str(scope or "").strip()
    if not raw or len(raw) > 512:
        raise ValueError("invalid_scope")
    if raw.startswith("room:"):
        room_id = raw[5:].strip()
        if not room_id or not can_access_room(conn, room_id, user_id):
            raise PermissionError("forbidden")
        return f"room:{room_id}", room_id
    if raw.startswith("dm:"):
        dm_key = raw[3:].strip()
        if not dm_key:
            raise ValueError("invalid_scope")
        # DM session identifiers are external Hermes ids. Namespacing them by
        # the authenticated user prevents another account from reading or
        # mutating a user's private interaction metadata.
        return f"dm:{user_id}:{dm_key}", None
    raise ValueError("invalid_scope")


def _reaction_rows(conn: sqlite3.Connection, scope_key: str, user_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT mr.message_id, mr.emoji, mr.user_id, mr.created_at,
               u.display_name, u.avatar_url
        FROM message_reactions AS mr
        LEFT JOIN users AS u ON u.id = mr.user_id
        WHERE mr.scope_key = ?
        ORDER BY mr.created_at, mr.emoji, mr.user_id
        """,
        (scope_key,),
    ).fetchall()
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        message_id = str(row["message_id"])
        emoji = str(row["emoji"])
        key = (message_id, emoji)
        reaction = grouped.setdefault(
            key,
            {
                "message_id": message_id,
                "emoji": emoji,
                "count": 0,
                "reacted": False,
                "reactors": [],
            },
        )
        reactor_user_id = str(row["user_id"])
        reaction["count"] += 1
        reaction["reacted"] = reaction["reacted"] or reactor_user_id == user_id
        reaction["reactors"].append(
            {
                "user_id": reactor_user_id,
                "display_name": str(row["display_name"] or "Member"),
                "avatar_url": row["avatar_url"],
            }
        )
    return list(grouped.values())


def list_reactions(
    conn: sqlite3.Connection,
    scope: str,
    user_id: str,
    can_access_room: RoomAccessCheck,
) -> dict[str, Any]:
    scope_key, _ = _resolved_scope(conn, scope, user_id, can_access_room)
    return {"ok": True, "reactions": _reaction_rows(conn, scope_key, user_id)}


def toggle_reaction(
    conn: sqlite3.Connection,
    scope: str,
    message_id: str,
    emoji: str,
    user_id: str,
    can_access_room: RoomAccessCheck,
) -> dict[str, Any]:
    clean_message_id = str(message_id or "").strip()
    clean_emoji = str(emoji or "").strip()
    if not clean_message_id or len(clean_message_id) > 512:
        raise ValueError("invalid_message_id")
    if not clean_emoji or len(clean_emoji) > 24:
        raise ValueError("invalid_emoji")

    scope_key, room_id = _resolved_scope(conn, scope, user_id, can_access_room)
    if room_id:
        exists = conn.execute(
            "SELECT 1 FROM messages WHERE id = ? AND room_id = ? AND deleted_at IS NULL",
            (clean_message_id, room_id),
        ).fetchone()
        if not exists:
            raise ValueError("message_not_found")

    existing = conn.execute(
        """
        SELECT 1 FROM message_reactions
        WHERE scope_key = ? AND message_id = ? AND user_id = ? AND emoji = ?
        """,
        (scope_key, clean_message_id, user_id, clean_emoji),
    ).fetchone()
    if existing:
        conn.execute(
            """
            DELETE FROM message_reactions
            WHERE scope_key = ? AND message_id = ? AND user_id = ? AND emoji = ?
            """,
            (scope_key, clean_message_id, user_id, clean_emoji),
        )
        reacted = False
    else:
        conn.execute(
            """
            INSERT INTO message_reactions (scope_key, message_id, user_id, emoji, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (scope_key, clean_message_id, user_id, clean_emoji, str(int(time.time()))),
        )
        reacted = True
    conn.commit()

    rows = [row for row in _reaction_rows(conn, scope_key, user_id) if row["message_id"] == clean_message_id]
    return {"ok": True, "reacted": reacted, "message_id": clean_message_id, "reactions": rows}
