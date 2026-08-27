"""WF-048 restore consistency checks for vault + binding state."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import credential_vault
import vault_kek


class RestoreValidationStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    MISSING_SECRET = "missing_secret"
    GENERATION_MISMATCH = "generation_mismatch"
    VAULT_UNAVAILABLE = "vault_unavailable"
    KEK_SEALED = "kek_sealed"


@dataclass(frozen=True)
class RestoreValidationResult:
    status: RestoreValidationStatus
    issues: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status is RestoreValidationStatus.OK


def _lease_generation_mismatch(
    conn: sqlite3.Connection,
    binding_id: str,
    capability_generation: int,
) -> bool:
    row = conn.execute(
        """SELECT MAX(capability_generation) FROM turn_credential_leases
            WHERE credential_binding_id = ? AND revoked_at IS NULL""",
        (binding_id,),
    ).fetchone()
    if not row or row[0] is None:
        return False
    return int(row[0] or 0) > int(capability_generation or 1)


def validate_restore_consistency(
    workframe_db: Path | str,
    *,
    vault_db: Path | str | None = None,
) -> RestoreValidationResult:
    """Verify restored workframe bindings align with vault secrets and lease generations."""
    workframe_path = Path(workframe_db)
    if not workframe_path.is_file():
        return RestoreValidationResult(RestoreValidationStatus.PARTIAL, ("workframe_db_missing",))

    original_vault_db = credential_vault.VAULT_DB
    original_data_dir = credential_vault.DATA_DIR
    issues: list[str] = []
    try:
        if vault_db is not None:
            vault_path = Path(vault_db)
            credential_vault.VAULT_DB = vault_path
            credential_vault.DATA_DIR = vault_path.parent
            credential_vault._SCHEMA_READY.clear()
            if not vault_path.is_file():
                return RestoreValidationResult(RestoreValidationStatus.PARTIAL, ("vault_db_missing",))

        if not vault_kek.kek_in_memory():
            status = credential_vault.vault_status()
            if status.get("passphrase_enabled"):
                return RestoreValidationResult(RestoreValidationStatus.KEK_SEALED, ("vault_sealed",))

        conn = sqlite3.connect(str(workframe_path), timeout=5.0)
        try:
            rows = conn.execute(
                """SELECT id, credential_ref, capability_generation, lifecycle_state
                     FROM credential_bindings
                    WHERE deleted_at IS NULL AND is_active = 1""",
            ).fetchall()
            for binding_id, credential_ref, generation, lifecycle_state in rows:
                binding_id = str(binding_id or "")
                vault_id = credential_vault.parse_vault_ref(str(credential_ref or ""))
                if not vault_id:
                    continue
                try:
                    read = credential_vault.read_secret_result(vault_id)
                except (OSError, RuntimeError, sqlite3.Error):
                    issues.append(f"vault_unavailable:{binding_id}")
                    continue
                if read.status is credential_vault.CredentialReadStatus.UNAVAILABLE:
                    issues.append(f"vault_unavailable:{binding_id}")
                elif read.status is credential_vault.CredentialReadStatus.SEALED:
                    return RestoreValidationResult(RestoreValidationStatus.KEK_SEALED, ("vault_sealed",))
                elif read.status in {
                    credential_vault.CredentialReadStatus.MISSING,
                    credential_vault.CredentialReadStatus.CORRUPT,
                }:
                    issues.append(f"missing_secret:{binding_id}")
                if str(lifecycle_state or "") == "active" and _lease_generation_mismatch(
                    conn, binding_id, int(generation or 1)
                ):
                    issues.append(f"generation_mismatch:{binding_id}")
        finally:
            conn.close()
    finally:
        credential_vault.VAULT_DB = original_vault_db
        credential_vault.DATA_DIR = original_data_dir
        credential_vault._SCHEMA_READY.clear()

    if not issues:
        return RestoreValidationResult(RestoreValidationStatus.OK)
    if any(issue.startswith("generation_mismatch:") for issue in issues):
        return RestoreValidationResult(RestoreValidationStatus.GENERATION_MISMATCH, tuple(issues))
    if any(issue.startswith("missing_secret:") for issue in issues):
        return RestoreValidationResult(RestoreValidationStatus.MISSING_SECRET, tuple(issues))
    if any(issue.startswith("vault_unavailable:") for issue in issues):
        return RestoreValidationResult(RestoreValidationStatus.VAULT_UNAVAILABLE, tuple(issues))
    return RestoreValidationResult(RestoreValidationStatus.PARTIAL, tuple(issues))
