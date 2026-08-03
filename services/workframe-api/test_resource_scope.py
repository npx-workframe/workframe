#!/usr/bin/env python3
"""WF-047 target-resource authorization regression.

Run: python services/workframe-api/test_resource_scope.py
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

_TEMP = tempfile.TemporaryDirectory(prefix="workframe-scope-")
os.environ["WORKFRAME_API_DATA_DIR"] = str(Path(_TEMP.name) / "api-data")
os.environ["WORKFRAME_DEPLOYMENT_MODE"] = "trusted_team"
os.environ["SECURE_MODE"] = "1"
os.environ.pop("DEV_LOCAL_UNSAFE", None)

import auth_gate  # noqa: E402

DB_PATH = Path(_TEMP.name) / "workframe.db"
INVITE_TOKEN = "invite-secret"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def seed() -> None:
    conn = connect()
    conn.executescript(
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            deleted_at TEXT
        );
        CREATE TABLE workspaces (
            id TEXT PRIMARY KEY,
            slug TEXT NOT NULL,
            status TEXT NOT NULL,
            deleted_at TEXT
        );
        CREATE TABLE workspace_memberships (
            workspace_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL,
            deleted_at TEXT
        );
        CREATE TABLE rooms (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            deleted_at TEXT
        );
        CREATE TABLE memory_items (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            created_by_user_id TEXT,
            deleted_at TEXT
        );
        CREATE TABLE agent_profiles (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            slug TEXT NOT NULL,
            deleted_at TEXT
        );
        CREATE TABLE workspace_invites (
            token_hash TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            email TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            accepted_at TEXT,
            deleted_at TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO users (id, email, role, deleted_at) VALUES (?, ?, ?, NULL)",
        [
            ("owner-a-member-b", "a@example.com", "owner"),
            ("owner-a-only", "a-only@example.com", "owner"),
            ("owner-b", "b-owner@example.com", "user"),
            ("member-b", "b-member@example.com", "user"),
            ("invitee", "invite@example.com", "user"),
        ],
    )
    conn.executemany(
        "INSERT INTO workspaces (id, slug, status, deleted_at) VALUES (?, ?, 'active', NULL)",
        [("ws-a", "a"), ("ws-b", "b")],
    )
    conn.executemany(
        """
        INSERT INTO workspace_memberships
            (workspace_id, user_id, role, status, deleted_at)
        VALUES (?, ?, ?, 'active', NULL)
        """,
        [
            ("ws-a", "owner-a-member-b", "owner"),
            ("ws-b", "owner-a-member-b", "member"),
            ("ws-a", "owner-a-only", "owner"),
            ("ws-b", "owner-b", "owner"),
            ("ws-b", "member-b", "member"),
        ],
    )
    conn.execute("INSERT INTO rooms (id, workspace_id, deleted_at) VALUES ('room-b', 'ws-b', NULL)")
    conn.execute(
        "INSERT INTO memory_items (id, workspace_id, created_by_user_id, deleted_at) "
        "VALUES ('memory-b', 'ws-b', 'member-b', NULL)"
    )
    conn.execute(
        "INSERT INTO agent_profiles (id, workspace_id, slug, deleted_at) "
        "VALUES ('agent-b', 'ws-b', 'architect', NULL)"
    )
    conn.execute(
        """
        INSERT INTO workspace_invites
            (token_hash, workspace_id, email, expires_at, accepted_at, deleted_at)
        VALUES (?, 'ws-b', 'invite@example.com', ?, NULL, NULL)
        """,
        (hashlib.sha256(INVITE_TOKEN.encode("utf-8")).hexdigest(), str(int(time.time()) + 3600)),
    )
    conn.commit()
    conn.close()


class FakeServer:
    def __init__(self) -> None:
        self.install_open = False

    def _workframe_db(self) -> sqlite3.Connection:
        return connect()

    def _install_window_open(self) -> bool:
        return self.install_open


class Handler:
    def __init__(self, user_id: str, method: str, path: str) -> None:
        self.command = method
        self.path = path
        self.headers = {"X-Workframe-Session": f"sid:{user_id}"}


seed()
fake_server = FakeServer()
original_srv = auth_gate._srv
original_validate = auth_gate._zk.validate_session_token
auth_gate._srv = lambda: fake_server
auth_gate._zk.validate_session_token = (
    lambda token: {"user_id": token[4:]} if token.startswith("sid:") else None
)


def authorize(user_id: str, method: str, path: str) -> Handler | None:
    handler = Handler(user_id, method, path)
    return handler if auth_gate.authorize_request(handler) else None


try:
    # Highest role in A never becomes authority in B.
    scoped = authorize("owner-a-member-b", "GET", "/api/workspace/ws-b/rooms")
    assert scoped is not None
    assert scoped.auth_workspace_id == "ws-b"
    assert scoped.auth_stack_role == "owner"
    assert scoped.auth_role == "member"
    assert authorize("owner-a-member-b", "GET", "/api/workspace/ws-b/credentials") is None
    assert authorize("owner-a-only", "GET", "/api/workspace/ws-b/rooms") is None

    # Member reads and collaboration writes remain available; admin/destructive writes do not.
    assert authorize("member-b", "GET", "/api/rooms/room-b/messages") is not None
    assert authorize("member-b", "POST", "/api/workspace/ws-b/memory") is not None
    assert authorize("member-b", "POST", "/api/workspace/ws-b/members") is None
    assert authorize("member-b", "DELETE", "/api/rooms/room-b") is None
    assert authorize("member-b", "DELETE", "/api/memory/memory-b") is None
    assert authorize("owner-b", "POST", "/api/workspace/ws-b/members") is not None
    assert authorize("owner-b", "DELETE", "/api/rooms/room-b") is not None
    assert authorize("owner-b", "DELETE", "/api/memory/memory-b") is not None

    # Indirect resource scopes resolve back to their owning workspace.
    assert authorize("owner-a-only", "GET", "/api/rooms/room-b/members") is None
    assert authorize("owner-a-only", "POST", "/api/memory/memory-b") is None
    assert authorize("owner-a-only", "GET", "/api/agents/agent-b/credentials") is None
    agent_admin = authorize("owner-b", "GET", "/api/agents/agent-b/credentials")
    assert agent_admin is not None and agent_admin.auth_role == "owner"

    # Invite metadata and acceptance are bound to the authenticated invited email.
    invited = authorize("invitee", "GET", f"/api/invites/{INVITE_TOKEN}")
    assert invited is not None
    assert invited.auth_workspace_id == "ws-b"
    assert invited.auth_role == "invited"
    assert authorize("owner-a-only", "GET", f"/api/invites/{INVITE_TOKEN}") is None
    assert authorize("invitee", "POST", f"/api/invites/{INVITE_TOKEN}/accept") is not None

    # Legacy public mutation paths are no longer public authority.
    assert authorize("owner-a-only", "POST", "/api/auth/bootstrap") is None
    fake_server.install_open = False
    assert authorize("owner-a-only", "POST", "/api/setup") is None
    fake_server.install_open = True
    assert authorize("owner-a-only", "POST", "/api/setup") is not None
    assert authorize("member-b", "POST", "/api/setup") is None

    # Helper no longer grants target access from a global-looking role on the handler.
    handler = Handler("owner-a-only", "GET", "/api/workspace/ws-b/rooms")
    handler.auth_user = "owner-a-only"
    handler.auth_role = "owner"
    assert not auth_gate.handler_is_active_workspace_member(handler, "ws-b")

    print("resource scope self-check ok")
finally:
    auth_gate._srv = original_srv
    auth_gate._zk.validate_session_token = original_validate
    _TEMP.cleanup()
