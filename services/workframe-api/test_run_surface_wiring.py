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
from domain.entities import RunSurface  # noqa: E402


def test_slash_audit_run_no_gate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "workframe.db"
        os.environ["WORKFRAME_API_DATA_DIR"] = tmp
        run_ledger.WORKFRAME_DB = db_path
        run_ledger._SCHEMA_READY.clear()
        assert run_surface_wiring.slash_requires_authority("help") is False
        assert run_surface_wiring.slash_requires_authority("chat") is True


def test_record_automated_cron() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "workframe.db"
        os.environ["WORKFRAME_API_DATA_DIR"] = tmp
        run_ledger.WORKFRAME_DB = db_path
        run_ledger._SCHEMA_READY.clear()
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


if __name__ == "__main__":
    test_slash_audit_run_no_gate()
    test_record_automated_cron()
    print("test_run_surface_wiring ok")
