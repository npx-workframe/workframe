"""WF-032 runtime_cohort self-check."""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

os.environ.setdefault("WORKFRAME_API_DATA_DIR", str(API_DIR / ".tmp-test-data"))
os.environ.setdefault("HERMES_DATA", str(API_DIR / ".tmp-test-hermes"))
os.environ.setdefault("DEV_LOCAL_UNSAFE", "true")

import runtime_cohort  # noqa: E402
import server  # noqa: E402


def test_runtime_profile_slug_format() -> None:
    slug = runtime_cohort._runtime_profile_slug("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "architect")
    assert slug.startswith("u-")
    assert slug.endswith("-architect")
    assert server._runtime_profile_slug("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "architect") == slug


def test_self_grant_forbidden() -> None:
    try:
        runtime_cohort.create_delegation_grant("ws-1", "user-1", "user-1")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "self_grant_forbidden"


def test_delegation_grant_round_trip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["WORKFRAME_API_DATA_DIR"] = tmp
        server.DATA_DIR = Path(tmp)
        server.AUTH_DB_PATH = Path(tmp) / "auth.db"
        server._ensure_workframe_db_schema()
        ws_id = str(uuid.uuid4())
        grantor = str(uuid.uuid4())
        grantee = str(uuid.uuid4())
        now = server._utc_now()
        conn = server._workframe_db()
        try:
            conn.execute(
                "INSERT INTO workspaces (id, slug, display_name, owner_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (ws_id, "test-ws", "Test", grantor, now, now),
            )
            for uid, email in ((grantor, "a@test.local"), (grantee, "b@test.local")):
                conn.execute(
                    "INSERT INTO users (id, email, display_name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (uid, email, email.split("@")[0], now, now),
                )
                conn.execute(
                    """
                    INSERT INTO workspace_memberships (
                        id, workspace_id, user_id, role, status, created_at, updated_at
                    ) VALUES (?, ?, ?, 'member', 'active', ?, ?)
                    """,
                    (str(uuid.uuid4()), ws_id, uid, now, now),
                )
            conn.commit()
        finally:
            conn.close()
        created = runtime_cohort.create_delegation_grant(ws_id, grantor, grantee)
        assert created["ok"] is True
        grant_id = created["grant"]["id"]
        listed = runtime_cohort.list_delegation_grants(ws_id, grantor)
        assert any(row["id"] == grant_id for row in listed["grants"])
        revoked = runtime_cohort.revoke_delegation_grant(ws_id, grant_id, grantor)
        assert revoked["ok"] is True
        grantors = runtime_cohort._delegation_grantor_ids_for_grantee(grantee, ws_id)
        assert grantor not in grantors


if __name__ == "__main__":
    test_runtime_profile_slug_format()
    test_self_grant_forbidden()
    test_delegation_grant_round_trip()
    print("test_runtime_cohort: ok")
