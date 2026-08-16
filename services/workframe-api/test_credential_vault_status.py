"""WF-048 typed vault read status matrix."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path

import credential_vault


def main() -> None:
    data_dir = Path(tempfile.mkdtemp(prefix="wf-vault-status-"))
    credential_vault.DATA_DIR = data_dir
    credential_vault.VAULT_DB = data_dir / "credential_vault.db"
    credential_vault._SCHEMA_READY.clear()
    credential_vault.unseal_for_tests()
    credential_vault.ensure_schema()

    assert credential_vault.read_secret_result("missing").status is credential_vault.CredentialReadStatus.MISSING
    credential_vault.store_secret("ok", "sk-test", provider="openrouter")
    result = credential_vault.read_secret_result("ok")
    assert result.status is credential_vault.CredentialReadStatus.OK and result.secret == "sk-test"

    conn = sqlite3.connect(str(credential_vault.VAULT_DB))
    conn.execute("UPDATE credential_secrets SET encrypted_secret = ? WHERE binding_id = ?", (json.dumps({"v": 2}), "ok"))
    conn.commit()
    conn.close()
    assert credential_vault.read_secret_result("ok").status is credential_vault.CredentialReadStatus.CORRUPT
    print("credential vault status matrix ok")


if __name__ == "__main__":
    main()
