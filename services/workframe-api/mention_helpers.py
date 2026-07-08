"""WF-032 extract: @mention handle resolution for space rooms."""

from __future__ import annotations

import re
import sqlite3
import threading
from typing import Any


def _srv():
    import server as srv

    return srv


def mention_handle(label: str, email: str = "") -> str:
    label = str(label or "").strip().lower()
    if label:
        handle = re.sub(r"[^a-z0-9]+", "", label.replace(" ", ""))
        if handle:
            return handle[:32]
    normalized = str(email or "").strip().lower()
    if normalized and "@" in normalized:
        local = normalized.split("@", 1)[0]
        handle = re.sub(r"[^a-z0-9]+", "", local)
        if handle:
            return handle[:32]
    return ""


def room_agents_for_mentions(
    conn: sqlite3.Connection,
    room_id: str,
    workspace_id: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT ap.id, ap.slug, ap.display_name, ap.model_provider, ap.model_name
        FROM room_memberships rm
        JOIN agent_profiles ap ON ap.id = rm.agent_profile_id
        WHERE rm.room_id = ? AND rm.deleted_at IS NULL AND ap.deleted_at IS NULL
        """,
        (room_id,),
    ).fetchall()
    if rows:
        return [dict(row) for row in rows]
    # ponytail: until membership backfill completes, allow all workspace agents in spaces
    fallback = conn.execute(
        """
        SELECT id, slug, display_name, model_provider, model_name
        FROM agent_profiles
        WHERE workspace_id = ? AND deleted_at IS NULL
        """,
        (workspace_id,),
    ).fetchall()
    return [dict(row) for row in fallback]


def room_users_for_mentions(conn: sqlite3.Connection, room_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT u.id, u.display_name, u.email
        FROM room_memberships rm
        JOIN users u ON u.id = rm.user_id
        WHERE rm.room_id = ? AND rm.deleted_at IS NULL AND rm.user_id IS NOT NULL
        """,
        (room_id,),
    ).fetchall()
    users: list[dict[str, Any]] = []
    for row in rows:
        users.append(
            {
                "id": str(row["id"]),
                "display_name": str(row["display_name"] or ""),
                "email": str(row["email"] or ""),
                "handle": mention_handle(str(row["display_name"] or ""), str(row["email"] or "")),
            }
        )
    return users


def parse_room_mentions(
    text: str,
    agents: list[dict[str, Any]],
    users: list[dict[str, Any]],
    *,
    triggered_by_user_id: str = "",
    workspace_id: str = "",
) -> dict[str, list[dict[str, Any]]]:
    """Resolve @handles in a space message to agents (invoke) and users (notify-only)."""
    handles = {m.group(1).lower() for m in re.finditer(r"@([\w-]+)", str(text or ""))}
    if not handles:
        return {"agents": [], "users": []}
    agent_by_handle: dict[str, dict[str, Any]] = {}
    for agent in agents:
        slug = str(agent.get("slug") or "").strip().lower()
        if slug:
            agent_by_handle[slug] = agent
        display = str(agent.get("display_name") or "").strip().lower()
        if display:
            agent_by_handle[display] = agent
            compact = re.sub(r"[^a-z0-9]+", "", display)
            if compact:
                agent_by_handle[compact] = agent
        if triggered_by_user_id and slug:
            personal = _srv()._runtime_display_label(triggered_by_user_id, slug, workspace_id).strip().lower()
            if personal:
                agent_by_handle[personal] = agent
                personal_compact = re.sub(r"[^a-z0-9]+", "", personal)
                if personal_compact:
                    agent_by_handle[personal_compact] = agent
    user_by_handle = {str(u["handle"]).lower(): u for u in users if u.get("handle")}
    matched_agents: list[dict[str, Any]] = []
    seen_agents: set[str] = set()
    for handle in handles:
        agent = agent_by_handle.get(handle)
        if agent and str(agent["id"]) not in seen_agents:
            seen_agents.add(str(agent["id"]))
            matched_agents.append(agent)
    matched_users: list[dict[str, Any]] = []
    seen_users: set[str] = set()
    for handle in handles:
        user = user_by_handle.get(handle)
        if user and str(user["id"]) not in seen_users:
            seen_users.add(str(user["id"]))
            matched_users.append(user)
    return {"agents": matched_agents, "users": matched_users}


def parse_mentions(text: str) -> list[dict]:
    """Extract @agent mentions from message text."""
    mentions = []
    for match in re.finditer(r"@(\w+)", text):
        slug = match.group(1)
        mentions.append({"type": "agent", "slug": slug})
    return mentions


def process_space_message_mentions(
    room_id: str,
    workspace_id: str,
    user_id: str,
    content: str,
    message_id: str,
    *,
    invoke_agents: bool = True,
) -> dict[str, Any]:
    conn = _srv()._workframe_db()
    try:
        agents = room_agents_for_mentions(conn, room_id, workspace_id)
        users = room_users_for_mentions(conn, room_id)
    finally:
        conn.close()
    mentions = parse_room_mentions(
        content,
        agents,
        users,
        triggered_by_user_id=user_id,
        workspace_id=workspace_id,
    )
    invoked: list[str] = []
    for agent in mentions["agents"]:
        invoked.append(str(agent["slug"]))
        if invoke_agents:
            threading.Thread(
                target=_srv()._invoke_room_agent_mention,
                kwargs={
                    "room_id": room_id,
                    "workspace_id": workspace_id,
                    "agent_row": agent,
                    "triggered_by_user_id": user_id,
                    "parent_message_id": message_id,
                },
                daemon=True,
            ).start()
    return {
        "agent_mentions": invoked,
        "user_mentions": [str(u.get("handle") or "") for u in mentions["users"]],
    }
