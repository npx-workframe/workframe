"""WF-NS-P2 run surface wiring self-check."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_ledger  # noqa: E402
import run_surface_wiring  # noqa: E402
import server  # noqa: E402
from domain.entities import ActorType, RunSurface  # noqa: E402


def _use_tmp_db(tmp: str) -> Path:
    db_path = Path(tmp) / "workframe.db"
    data = Path(tmp)
    os.environ["WORKFRAME_API_DATA_DIR"] = tmp
    server.DATA_DIR = data
    server.AUTH_DB_PATH = data / "auth.db"
    run_ledger.DATA_DIR = data
    run_ledger.WORKFRAME_DB = db_path
    run_ledger._SCHEMA_READY.clear()
    return db_path


def _line_items_for_run(db_path: Path, run_id: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT kind, amount_usd, receipt_json FROM run_line_items WHERE run_id = ?",
            (run_id,),
        ).fetchall()
    finally:
        conn.close()


def test_slash_audit_run_no_gate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _use_tmp_db(tmp)
        assert run_surface_wiring.slash_requires_authority("help") is False
        assert run_surface_wiring.slash_requires_authority("chat") is True


def test_record_automated_cron() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = _use_tmp_db(tmp)
        run_ledger.ensure_schema()
        result = run_surface_wiring.record_automated_surface_run(
            {
                "surface": "cron",
                "profile_slug": "u-test-dev",
                "triggering_user_id": "user-1",
                "workspace_id": "ws-1",
                "actor_id": "cron:daily",
                "provider": "openrouter",
                "event_type": "cron.triggered",
                "payload": {"job": "daily"},
            }
        )
        assert result["ok"] is True
        rid = str(result["run_id"])
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT surface, status FROM runs WHERE run_id = ?", (rid,)).fetchone()
        conn.close()
        assert row is not None
        assert row["surface"] == RunSurface.CRON.value
        assert row["status"] == "completed"
        items = _line_items_for_run(db_path, rid)
        assert len(items) == 1
        assert items[0]["amount_usd"] is None


def test_finish_surface_run_emits_receipt() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = _use_tmp_db(tmp)
        run_ledger.ensure_schema()
        rid = run_surface_wiring.record_audit_surface_run(
            surface=RunSurface.SLASH,
            actor_type=ActorType.USER,
            actor_id="user-1",
            triggering_user_id="user-1",
            profile_slug="u-test-dev",
            workspace_id="ws-1",
            event_type="slash.command",
            payload={"command": "help"},
            provider="openrouter",
        )
        run_surface_wiring.finish_surface_run(rid, ok=True, detail="ok")
        items = _line_items_for_run(db_path, rid)
        assert len(items) == 1
        assert items[0]["amount_usd"] is None


def test_record_automated_webhook() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _use_tmp_db(tmp)
        run_ledger.ensure_schema()
        result = run_surface_wiring.record_automated_surface_run(
            {
                "surface": "webhook",
                "profile_slug": "u-test-dev",
                "triggering_user_id": "user-1",
                "workspace_id": "ws-1",
                "actor_id": "webhook:github",
                "event_type": "webhook.received",
                "provider": "openrouter",
                "payload": {"source": "github"},
            }
        )
        assert result["ok"] is True
        assert result["surface"] == RunSurface.WEBHOOK.value
        rid = str(result["run_id"])
        items = _line_items_for_run(Path(tmp) / "workframe.db", rid)
        assert len(items) == 1
        assert items[0]["amount_usd"] is None


if __name__ == "__main__":
    test_slash_audit_run_no_gate()
    test_record_automated_cron()
    test_record_automated_webhook()
    test_finish_surface_run_emits_receipt()
    print("test_run_surface_wiring ok")
