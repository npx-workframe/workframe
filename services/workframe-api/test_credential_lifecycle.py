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
    conn.execute("ALTER TABLE credential_bindings ADD COLUMN credential_ref TEXT DEFAULT 'vault:b1'")
    conn.execute("ALTER TABLE credential_bindings ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    conn.execute("ALTER TABLE credential_bindings ADD COLUMN deleted_at TEXT")
    conn.execute("ALTER TABLE credential_bindings ADD COLUMN updated_at TEXT")
    conn.execute("ALTER TABLE credential_bindings ADD COLUMN lifecycle_updated_at TEXT")
    conn.execute("ALTER TABLE credential_bindings ADD COLUMN expires_at TEXT")
    conn.execute("INSERT INTO credential_bindings (id, capability_generation, lifecycle_state, credential_ref, expires_at) VALUES ('b2', 1, 'active', 'vault:b2', '1970-01-01T00:00:00+00:00')")
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

    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO credential_bindings (id, capability_generation, lifecycle_state, credential_ref, is_active) VALUES ('b3', 1, 'staged', 'vault:b3', 0)"
    )
    conn.commit()
    conn.close()
    operation_id = credential_lifecycle.begin_operation("b3", "create")
    credential_lifecycle.credential_vault.read_secret_result = lambda _binding_id: credential_lifecycle.credential_vault.CredentialReadResult(credential_lifecycle.credential_vault.CredentialReadStatus.OK, "opaque")
    pending = credential_lifecycle.recover_pending_operations()
    assert any(item["operation_id"] == operation_id for item in pending)
    conn = sqlite3.connect(str(db))
    state = conn.execute("SELECT state FROM credential_lifecycle_operations WHERE operation_id = ?", (operation_id,)).fetchone()[0]
    binding_state = conn.execute("SELECT lifecycle_state, is_active FROM credential_bindings WHERE id = 'b3'").fetchone()
    conn.close()
    assert state == "completed" and binding_state == ("active", 1)

    deleted: list[str] = []
    credential_lifecycle.credential_vault.delete_secret = lambda binding_id: deleted.append(binding_id)
    credential_lifecycle.turn_credentials.revoke_matching_leases = lambda **_kwargs: 1
    assert credential_lifecycle.revoke_binding("b2", reason="test")
    conn = sqlite3.connect(str(db))
    row = conn.execute("SELECT capability_generation, lifecycle_state, is_active FROM credential_bindings WHERE id = 'b2'").fetchone()
    conn.close()
    assert row == (2, "revoked", 0)
    assert deleted == ["b2"]
    print("credential lifecycle operations ok")


if __name__ == "__main__":
    main()
