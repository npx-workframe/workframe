"""WF-048 durable lifecycle operation self-check."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path
from types import ModuleType

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    db = Path(tempfile.mkdtemp(prefix="wf-lifecycle-") ) / "workframe.db"
    fake = ModuleType("server")
    fake._workframe_db_path = lambda: db  # type: ignore[attr-defined]
    fake._utc_now = lambda: "2026-01-01T00:00:00+00:00"  # type: ignore[attr-defined]
    sys.modules["server"] = fake
    import credential_lifecycle

    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE credential_bindings (id TEXT PRIMARY KEY, capability_generation INTEGER, lifecycle_state TEXT)")
    conn.execute("""CREATE TABLE credential_lifecycle_operations (
        operation_id TEXT PRIMARY KEY, binding_id TEXT NOT NULL, operation_type TEXT NOT NULL,
        state TEXT NOT NULL, capability_generation INTEGER NOT NULL, details_json TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    conn.execute("INSERT INTO credential_bindings VALUES ('b1', 2, 'active')")
    conn.commit()
    conn.close()

    operation_id = credential_lifecycle.begin_operation("b1", "replace")
    credential_lifecycle.transition_operation(operation_id, "bound")
    pending = credential_lifecycle.recover_pending_operations()
    assert pending and pending[0]["operation_id"] == operation_id

    conn = sqlite3.connect(str(db))
    state = conn.execute("SELECT state FROM credential_lifecycle_operations WHERE operation_id = ?", (operation_id,)).fetchone()[0]
    conn.close()
    assert state == "failed"
    print("credential lifecycle operations ok")


if __name__ == "__main__":
    main()
