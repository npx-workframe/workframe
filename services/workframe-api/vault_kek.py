"""Vault master key (KEK) — in-memory only; separate from ZK_AUTH_ENCRYPTION_KEY."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DATA_DIR = Path(os.environ.get("WORKFRAME_API_DATA_DIR", "/app/data"))
VAULT_KEK_FILE = DATA_DIR / ".vault_kek"
META_TABLE = "vault_meta"

_KEK: bytes | None = None
_PBKDF2_ROUNDS = 200_000


def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64d(value: str) -> bytes:
    raw = base64.b64decode(str(value or "").strip())
    if len(raw) != 32:
        raise ValueError("vault KEK must be 32 bytes")
    return raw


def _derive_wrap_key(passphrase: str, salt: bytes) -> bytes:
    phrase = str(passphrase or "")
    if len(phrase) < 12:
        raise ValueError("passphrase must be at least 12 characters")
    return hashlib.pbkdf2_hmac("sha256", phrase.encode("utf-8"), salt, _PBKDF2_ROUNDS, dklen=32)


def _aes_gcm_encrypt(key: bytes, plaintext: bytes) -> dict[str, str]:
    iv = os.urandom(12)
    ct = AESGCM(key).encrypt(iv, plaintext, None)
    return {
        "v": 1,
        "alg": "AES-256-GCM",
        "iv": _b64e(iv),
        "tag": _b64e(ct[-16:]),
        "ciphertext": _b64e(ct[:-16]),
    }


def _aes_gcm_decrypt(key: bytes, payload: dict[str, Any]) -> bytes:
    if int(payload.get("v") or 0) != 1 or str(payload.get("alg") or "") != "AES-256-GCM":
        raise ValueError("unsupported wrap payload")
    iv = base64.b64decode(str(payload["iv"]))
    tag = base64.b64decode(str(payload["tag"]))
    ct = base64.b64decode(str(payload["ciphertext"]))
    return AESGCM(key).decrypt(iv, ct + tag, None)


def kek_in_memory() -> bool:
    return _KEK is not None


def get_kek() -> bytes:
    if _KEK is None:
        raise RuntimeError("vault_sealed")
    return _KEK


def set_kek(raw: bytes) -> None:
    global _KEK
    if len(raw) != 32:
        raise ValueError("KEK must be 32 bytes")
    _KEK = bytes(raw)


def clear_kek() -> None:
    global _KEK
    _KEK = None


def load_kek_from_env() -> bool:
    raw = os.environ.get("WORKFRAME_VAULT_KEK", "").strip()
    if not raw:
        return False
    set_kek(_b64d(raw))
    return True


def load_kek_from_file() -> bool:
    if not VAULT_KEK_FILE.is_file():
        return False
    try:
        text = VAULT_KEK_FILE.read_text(encoding="utf-8").strip()
        payload = json.loads(text) if text.startswith("{") else {"key": text}
        key_b64 = str(payload.get("key") or text).strip()
        set_kek(_b64d(key_b64))
        return True
    except Exception:
        return False


def persist_kek_file() -> None:
    """Persist in-memory KEK for single-tenant bootstrap (chmod 600)."""
    if _KEK is None:
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VAULT_KEK_FILE.write_text(
        json.dumps({"v": 1, "key": _b64e(_KEK)}),
        encoding="utf-8",
    )
    try:
        os.chmod(VAULT_KEK_FILE, 0o600)
    except OSError:
        pass


def generate_and_persist_kek() -> bytes:
    set_kek(os.urandom(32))
    persist_kek_file()
    return get_kek()


def wrap_kek_for_passphrase(passphrase: str) -> tuple[str, str]:
    """Return (salt_b64, wrapped_kek_json) for vault_meta."""
    if _KEK is None:
        raise RuntimeError("vault_sealed")
    salt = os.urandom(16)
    wrap_key = _derive_wrap_key(passphrase, salt)
    wrapped = _aes_gcm_encrypt(wrap_key, _KEK)
    return _b64e(salt), json.dumps(wrapped)


def unwrap_kek_from_passphrase(passphrase: str, salt_b64: str, wrapped_json: str) -> bytes:
    salt = base64.b64decode(str(salt_b64 or "").strip())
    wrap_key = _derive_wrap_key(passphrase, salt)
    payload = json.loads(wrapped_json)
    return _aes_gcm_decrypt(wrap_key, payload)


def unseal_for_tests() -> None:
    """Tests: deterministic KEK without touching disk."""
    seed = os.environ.get("WORKFRAME_VAULT_KEK", "").strip()
    if seed:
        set_kek(_b64d(seed))
        return
    set_kek(hashlib.sha256(b"workframe-test-vault-kek").digest())


if __name__ == "__main__":
    generate_and_persist_kek()
    assert kek_in_memory()
    salt, wrapped = wrap_kek_for_passphrase("test-passphrase-12")
    clear_kek()
    set_kek(unwrap_kek_from_passphrase("test-passphrase-12", salt, wrapped))
    assert kek_in_memory()
    print("vault_kek ok")
