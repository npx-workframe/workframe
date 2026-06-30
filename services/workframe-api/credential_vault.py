"""API-only credential vault — envelope-encrypted secrets (KEK + per-secret DEK)."""

from __future__ import annotations

import base64
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

import vault_kek
import zk_auth

DATA_DIR = Path(os.environ.get("WORKFRAME_API_DATA_DIR", "/app/data"))
VAULT_DB = DATA_DIR / "credential_vault.db"
LEGACY_V1 = 1
ENVELOPE_V2 = 2


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(VAULT_DB), timeout=5.0)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _meta_row(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM vault_meta WHERE id = 1").fetchone()


# ponytail: ran on every read_secret/store (and again via turn_credentials) — ~11ms/call on
# bind-mounted sqlite. Guard by DB path: once per process, tests reassign VAULT_DB → re-run.
_SCHEMA_READY: set[str] = set()


def ensure_schema() -> None:
    key = str(VAULT_DB)
    if key in _SCHEMA_READY:
        return
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS credential_secrets (
                binding_id TEXT PRIMARY KEY,
                encrypted_secret TEXT NOT NULL,
                env_var TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                scope TEXT NOT NULL DEFAULT 'user',
                user_id TEXT DEFAULT NULL,
                workspace_id TEXT DEFAULT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_credential_secrets_user "
            "ON credential_secrets(user_id, provider)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vault_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                initialized INTEGER NOT NULL DEFAULT 0,
                passphrase_enabled INTEGER NOT NULL DEFAULT 0,
                kdf_salt TEXT DEFAULT NULL,
                wrapped_kek TEXT DEFAULT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        if not _meta_row(conn):
            now = str(int(time.time()))
            conn.execute(
                """
                INSERT INTO vault_meta (id, initialized, passphrase_enabled, created_at, updated_at)
                VALUES (1, 0, 0, ?, ?)
                """,
                (now, now),
            )
        conn.commit()
    finally:
        conn.close()
    _SCHEMA_READY.add(key)


def vault_status() -> dict[str, Any]:
    ensure_schema()
    conn = _connect()
    try:
        meta = _meta_row(conn)
        count = int(conn.execute("SELECT COUNT(*) FROM credential_secrets").fetchone()[0])
    finally:
        conn.close()
    initialized = bool(meta and int(meta["initialized"] or 0))
    return {
        "sealed": not vault_kek.kek_in_memory(),
        "initialized": initialized,
        "passphrase_enabled": bool(meta and int(meta["passphrase_enabled"] or 0)),
        "secret_count": count,
        "kek_file_present": vault_kek.VAULT_KEK_FILE.is_file(),
        "env_kek_configured": bool(os.environ.get("WORKFRAME_VAULT_KEK", "").strip()),
    }


def _require_unsealed() -> None:
    if not vault_kek.kek_in_memory():
        raise RuntimeError("vault_sealed")


def _encrypt_dek_with_kek(dek: bytes) -> dict[str, str]:
    kek = vault_kek.get_kek()
    iv = os.urandom(12)
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    ct = AESGCM(kek).encrypt(iv, dek, None)
    return {
        "iv": base64.b64encode(iv).decode("ascii"),
        "tag": base64.b64encode(ct[-16:]).decode("ascii"),
        "ciphertext": base64.b64encode(ct[:-16]).decode("ascii"),
    }


def _decrypt_dek_with_kek(wrapped: dict[str, Any]) -> bytes:
    kek = vault_kek.get_kek()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    iv = base64.b64decode(str(wrapped["iv"]))
    tag = base64.b64decode(str(wrapped["tag"]))
    ct = base64.b64decode(str(wrapped["ciphertext"]))
    dek = AESGCM(kek).decrypt(iv, ct + tag, None)
    if len(dek) != 32:
        raise ValueError("invalid DEK length")
    return dek


def _encrypt_v2(secret: str) -> str:
    dek = os.urandom(32)
    dek_b64 = base64.b64encode(dek).decode("ascii")
    payload = zk_auth.encrypt_string(str(secret or ""), dek_b64)
    envelope = {
        "v": ENVELOPE_V2,
        "alg": "envelope-aes-gcm",
        "wrapped_dek": _encrypt_dek_with_kek(dek),
        "payload": payload,
    }
    return json.dumps(envelope)


def _decrypt_v2(blob: str) -> str:
    envelope = json.loads(blob)
    if int(envelope.get("v") or 0) != ENVELOPE_V2:
        raise ValueError("not v2 envelope")
    dek_b64 = base64.b64encode(_decrypt_dek_with_kek(envelope["wrapped_dek"])).decode("ascii")
    return zk_auth.decrypt_string(envelope["payload"], dek_b64)


def _decrypt_legacy_v1(blob: str) -> str:
    payload = json.loads(blob) if isinstance(blob, str) else blob
    if not isinstance(payload, dict):
        return ""
    if int(payload.get("v") or 0) == ENVELOPE_V2:
        return _decrypt_v2(blob)
    return zk_auth.decrypt_string(payload, zk_auth.ZK_AUTH_ENCRYPTION_KEY)


def _encrypt(secret: str) -> str:
    _require_unsealed()
    return _encrypt_v2(secret)


def _decrypt(blob: str) -> str:
    if not str(blob or "").strip():
        return ""
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError:
        return ""
    version = int(parsed.get("v") or LEGACY_V1) if isinstance(parsed, dict) else LEGACY_V1
    if version == ENVELOPE_V2:
        if not vault_kek.kek_in_memory():
            return ""
        return _decrypt_v2(blob)
    return _decrypt_legacy_v1(blob)


def _mark_initialized(passphrase_enabled: bool = False, salt_b64: str = "", wrapped: str = "") -> None:
    now = str(int(time.time()))
    conn = _connect()
    try:
        conn.execute(
            """
            UPDATE vault_meta
            SET initialized = 1,
                passphrase_enabled = ?,
                kdf_salt = ?,
                wrapped_kek = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (1 if passphrase_enabled else 0, salt_b64 or None, wrapped or None, now),
        )
        conn.commit()
    finally:
        conn.close()


def bootstrap_vault(*, allow_generate_file: bool = True) -> dict[str, Any]:
    """Load KEK from env or .vault_kek; optionally generate file on first boot."""
    ensure_schema()
    if vault_kek.kek_in_memory():
        return vault_status()
    if vault_kek.load_kek_from_env():
        _mark_initialized(passphrase_enabled=False)
        return vault_status()
    if vault_kek.load_kek_from_file():
        _mark_initialized(passphrase_enabled=False)
        return vault_status()
    if allow_generate_file and not vault_status()["initialized"]:
        vault_kek.generate_and_persist_kek()
        _mark_initialized(passphrase_enabled=False)
        return vault_status()
    return vault_status()


def init_vault_passphrase(passphrase: str) -> dict[str, Any]:
    ensure_schema()
    status = vault_status()
    if status["passphrase_enabled"]:
        raise ValueError("vault_passphrase_already_set")
    if not vault_kek.kek_in_memory():
        if not vault_kek.load_kek_from_env() and not vault_kek.load_kek_from_file():
            vault_kek.generate_and_persist_kek()
    salt, wrapped = vault_kek.wrap_kek_for_passphrase(passphrase)
    _mark_initialized(passphrase_enabled=True, salt_b64=salt, wrapped=wrapped)
    _reencrypt_all_secrets()
    return vault_status()


def unlock_vault(passphrase: str) -> dict[str, Any]:
    ensure_schema()
    conn = _connect()
    try:
        meta = _meta_row(conn)
    finally:
        conn.close()
    if not meta or not int(meta["passphrase_enabled"] or 0):
        raise ValueError("vault_passphrase_not_configured")
    kek = vault_kek.unwrap_kek_from_passphrase(
        passphrase,
        str(meta["kdf_salt"] or ""),
        str(meta["wrapped_kek"] or ""),
    )
    vault_kek.set_kek(kek)
    return vault_status()


def seal_vault() -> dict[str, Any]:
    vault_kek.clear_kek()
    return vault_status()


def wipe_all_secrets() -> int:
    """Emergency delete — ciphertext only; bindings remain but secrets are gone."""
    ensure_schema()
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM credential_secrets")
        conn.commit()
        return int(cur.rowcount)
    finally:
        conn.close()


def _reencrypt_all_secrets() -> int:
    _require_unsealed()
    conn = _connect()
    migrated = 0
    try:
        rows = conn.execute(
            "SELECT binding_id, encrypted_secret FROM credential_secrets"
        ).fetchall()
        now = str(int(time.time()))
        for row in rows:
            plain = _decrypt(str(row["encrypted_secret"] or ""))
            if not plain:
                continue
            enc = _encrypt_v2(plain)
            conn.execute(
                "UPDATE credential_secrets SET encrypted_secret = ?, updated_at = ? WHERE binding_id = ?",
                (enc, now, str(row["binding_id"])),
            )
            migrated += 1
        conn.commit()
    finally:
        conn.close()
    return migrated


def store_secret(
    binding_id: str,
    secret: str,
    *,
    env_var: str = "",
    provider: str = "",
    scope: str = "user",
    user_id: str = "",
    workspace_id: str = "",
) -> None:
    binding_id = str(binding_id or "").strip()
    if not binding_id:
        raise ValueError("binding_id required")
    if not str(secret or "").strip():
        raise ValueError("secret required")
    if not vault_kek.kek_in_memory():
        status = vault_status()
        if status["passphrase_enabled"]:
            raise RuntimeError("vault_sealed")
        bootstrap_vault(allow_generate_file=True)
    _require_unsealed()
    ensure_schema()
    now = str(int(time.time()))
    enc = _encrypt(secret)
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO credential_secrets (
                binding_id, encrypted_secret, env_var, provider, scope,
                user_id, workspace_id, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(binding_id) DO UPDATE SET
                encrypted_secret = excluded.encrypted_secret,
                env_var = excluded.env_var,
                provider = excluded.provider,
                scope = excluded.scope,
                user_id = excluded.user_id,
                workspace_id = excluded.workspace_id,
                updated_at = excluded.updated_at
            """,
            (
                binding_id,
                enc,
                str(env_var or ""),
                str(provider or ""),
                str(scope or "user"),
                str(user_id or "") or None,
                str(workspace_id or "") or None,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def read_secret(binding_id: str) -> str:
    binding_id = str(binding_id or "").strip()
    if not binding_id:
        return ""
    ensure_schema()
    if not vault_kek.kek_in_memory():
        status = vault_status()
        if status["passphrase_enabled"]:
            return ""
        bootstrap_vault(allow_generate_file=True)
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT encrypted_secret FROM credential_secrets WHERE binding_id = ?",
            (binding_id,),
        ).fetchone()
        if not row:
            return ""
        blob = str(row["encrypted_secret"] or "")
        plain = _decrypt(blob)
        if not plain or not vault_kek.kek_in_memory():
            return plain
        try:
            parsed = json.loads(blob)
            if isinstance(parsed, dict) and int(parsed.get("v") or 0) != ENVELOPE_V2:
                enc = _encrypt_v2(plain)
                now = str(int(time.time()))
                conn.execute(
                    "UPDATE credential_secrets SET encrypted_secret = ?, updated_at = ? WHERE binding_id = ?",
                    (enc, now, binding_id),
                )
                conn.commit()
        except json.JSONDecodeError:
            pass
        return plain
    finally:
        conn.close()


def delete_secret(binding_id: str) -> None:
    binding_id = str(binding_id or "").strip()
    if not binding_id:
        return
    ensure_schema()
    conn = _connect()
    try:
        conn.execute("DELETE FROM credential_secrets WHERE binding_id = ?", (binding_id,))
        conn.commit()
    finally:
        conn.close()


def vault_ref(binding_id: str) -> str:
    return f"vault:{binding_id}"


def unseal_for_tests() -> None:
    """Deterministic KEK for unit tests."""
    vault_kek.unseal_for_tests()


def parse_vault_ref(credential_ref: str) -> str:
    ref = str(credential_ref or "").strip()
    if ref.startswith("vault:"):
        return ref[6:].strip()
    return ""


if __name__ == "__main__":
    vault_kek.unseal_for_tests()
    ensure_schema()
    bid = "__selfcheck__"
    store_secret(bid, "sk-test", env_var="OPENROUTER_API_KEY", provider="openrouter")
    assert read_secret(bid) == "sk-test"
    blob = _connect().execute(
        "SELECT encrypted_secret FROM credential_secrets WHERE binding_id = ?",
        (bid,),
    ).fetchone()["encrypted_secret"]
    assert '"v": 2' in blob or '"v":2' in blob.replace(" ", "")
    delete_secret(bid)
    assert read_secret(bid) == ""
    print("credential_vault ok")
