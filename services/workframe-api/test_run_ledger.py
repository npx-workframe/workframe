"""WF-NS-P2 run ledger self-check."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_ledger  # noqa: E402
from domain.entities import (  # noqa: E402
    ActorType,
    FundingSource,
    RunStatus,
    RunSurface,
)
from run_authority import RunAuthorityDecision, chat_run_request  # noqa: E402


def test_schema_and_round_trip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "workframe.db"
        os.environ["WORKFRAME_API_DATA_DIR"] = tmp
        run_ledger.WORKFRAME_DB = db_path
        run_ledger._SCHEMA_READY.clear()
        run_ledger.ensure_schema()

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            decision = RunAuthorityDecision(
                allowed=True,
                deny_reason=None,
                payer_user_id="user-1",
                funding_source=FundingSource.BYOK,
                credential_ref_id=None,
                credential_scope="user",
                grants=(),
            )
            run_ledger.record_authority_decision(
                conn,
                run_id="run-test-1",
                request_surface=RunSurface.CHAT,
                actor_type=ActorType.USER,
                actor_id="user-1",
                triggering_user_id="user-1",
                workspace_id="ws-1",
                agent_id="agent-1",
                runtime_binding_id="bind-1",
                profile_slug="u-user-1-native",
                provider="openrouter",
                room_id="room-1",
                session_id="sess-1",
                decision=decision,
            )
            conn.commit()

            run = run_ledger.get_run(conn, "run-test-1")
            assert run is not None
            assert run.status == RunStatus.RUNNING
            assert run.funding_source == FundingSource.BYOK

            run_ledger.complete_run(
                conn,
                "run-test-1",
                model="test/model",
                provider="openrouter",
                funding_source=FundingSource.BYOK,
                payer_user_id="user-1",
            )
            conn.commit()

            items = conn.execute(
                "SELECT kind, funding_source, amount_usd, receipt_json FROM run_line_items WHERE run_id = ?",
                ("run-test-1",),
            ).fetchall()
            assert len(items) == 1
            assert str(items[0]["kind"]) == "llm_turn"
            assert items[0]["amount_usd"] is None
            receipt = json.loads(str(items[0]["receipt_json"]))
            assert receipt["run_id"] == "run-test-1"
            assert receipt["payer_user_id"] == "user-1"
        finally:
            conn.close()

        events = run_ledger.list_run_events_for_room("room-1")
        assert len(events) >= 2
        assert events[0]["source"] == "run_ledger"


def test_dm_room_chat_run_recorded() -> None:
    """WF-NS-P2: DM rooms (room_type=direct) share chat_stream run path."""
    dm_room_id = "550e8400-e29b-41d4-a716-446655440099"
    req = chat_run_request(
        triggering_user_id="user-a",
        profile_slug="u-user-a-native",
        workspace_id="ws-1",
        provider="openrouter",
        room_id=dm_room_id,
    )
    assert req.surface == RunSurface.CHAT

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "workframe.db"
        os.environ["WORKFRAME_API_DATA_DIR"] = tmp
        run_ledger.WORKFRAME_DB = db_path
        run_ledger._SCHEMA_READY.clear()
        run_ledger.ensure_schema()

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            decision = RunAuthorityDecision(
                allowed=True,
                deny_reason=None,
                payer_user_id="user-a",
                funding_source=FundingSource.BYOK,
                credential_ref_id=None,
                credential_scope="user",
                grants=(),
            )
            run_ledger.record_authority_decision(
                conn,
                run_id="run-dm-1",
                request_surface=req.surface,
                actor_type=req.actor_type,
                actor_id=req.actor_id,
                triggering_user_id="user-a",
                workspace_id="ws-1",
                agent_id=req.agent_id,
                runtime_binding_id=req.runtime_binding_id,
                profile_slug=req.profile_slug,
                provider="openrouter",
                room_id=dm_room_id,
                session_id="sess-dm-1",
                decision=decision,
            )
            conn.commit()
            row = conn.execute(
                "SELECT surface, room_id FROM runs WHERE run_id = ?",
                ("run-dm-1",),
            ).fetchone()
            assert row is not None
            assert row["surface"] == RunSurface.CHAT.value
            assert row["room_id"] == dm_room_id
        finally:
            conn.close()


if __name__ == "__main__":
    test_schema_and_round_trip()
    test_dm_room_chat_run_recorded()
    print("test_run_ledger: ok")
