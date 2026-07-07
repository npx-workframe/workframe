"""
zk-auth compatible auth module for Workframe API.

Ported from /d/ab/projects/zk-auth/ with the same:
- AES-256-GCM encryption for secrets (emails, tokens)
- HMAC-SHA256 for email hashing, OTP hashing, token hashing
- Atomic OTP consume with attempt counting
- Session management with refresh tokens
- Profile management (display_name, avatar_url, tagline, bio)

Two modes:
- DEV_LOCAL_UNSAFE: OTP is returned in response (no email needed)
- SECURE_MODE: OTP is sent via email (requires SMTP config)
"""

from __future__ import annotations

import base64
import hmac as _hmac_mod
import json
import os
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_DIR = os.environ.get("WORKFRAME_API_DATA_DIR", "/app/data")
AUTH_KEYS_FILE = os.path.join(DATA_DIR, ".auth_keys")


def _load_or_generate_keys() -> tuple[str, str, str]:
    """Load auth keys from env, disk, or generate on first boot."""
    hmac_env = os.environ.get("ZK_AUTH_HMAC_KEY", "").strip()
    enc_env = os.environ.get("ZK_AUTH_ENCRYPTION_KEY", "").strip()
    session_env = os.environ.get("ZK_AUTH_SESSION_SECRET", "").strip()
    if hmac_env and enc_env and session_env:
        return hmac_env, enc_env, session_env

    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(AUTH_KEYS_FILE):
        try:
            with open(AUTH_KEYS_FILE, "r") as f:
                keys = json.load(f)
            return keys["hmac"], keys["enc"], keys["session"]
        except Exception:
            pass
    # First boot — generate and persist
    hmac_key = secrets.token_hex(32)
    enc_key = base64.b64encode(os.urandom(32)).decode()
    session_key = secrets.token_hex(32)
    try:
        with open(AUTH_KEYS_FILE, "w") as f:
            json.dump({"hmac": hmac_key, "enc": enc_key, "session": session_key}, f)
        os.chmod(AUTH_KEYS_FILE, 0o600)
    except Exception:
        pass  # container may be read-only; fall back to in-memory
    return hmac_key, enc_key, session_key


ZK_AUTH_HMAC_KEY, ZK_AUTH_ENCRYPTION_KEY, ZK_AUTH_SESSION_SECRET = _load_or_generate_keys()
OTP_TTL_MINUTES = int(os.environ.get("OTP_TTL_MINUTES", "10"))
SESSION_TTL_DAYS = int(os.environ.get("SESSION_TTL_DAYS", "30"))
OTP_MAX_ATTEMPTS = 5


# ---------------------------------------------------------------------------
# Crypto (ported from zk-auth/src/crypto/)
# ---------------------------------------------------------------------------


def _decode_aes256_key(value: str) -> bytes:
    key = base64.b64decode(value)
    if len(key) != 32:
        raise ValueError("ZK_AUTH_ENCRYPTION_KEY must be a base64-encoded 32-byte key.")
    return key


def encrypt_string(value: str, secret: str) -> dict:
    """AES-256-GCM encrypt. Returns {v, alg, iv, tag, ciphertext}."""
    key = _decode_aes256_key(secret)
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(iv, value.encode("utf8"), None)
    return {
        "v": 1,
        "alg": "AES-256-GCM",
        "iv": base64.b64encode(iv).decode("ascii"),
        "tag": base64.b64encode(ct[-16:]).decode("ascii"),
        "ciphertext": base64.b64encode(ct[:-16]).decode("ascii"),
    }


def decrypt_string(payload: dict, secret: str) -> str:
    """AES-256-GCM decrypt."""
    if payload.get("v") != 1 or payload.get("alg") != "AES-256-GCM":
        raise ValueError("Unsupported encrypted payload format.")
    key = _decode_aes256_key(secret)
    iv = base64.b64decode(payload["iv"])
    tag = base64.b64decode(payload["tag"])
    ct = base64.b64decode(payload["ciphertext"])
    aesgcm = AESGCM(key)
    pt = aesgcm.decrypt(iv, ct + tag, None)
    return pt.decode("utf8")


def hmac_sha256(secret: str, value: str) -> str:
    return _hmac_mod.new(secret.encode("utf8"), value.encode("utf8"), "sha256").hexdigest()


def hash_email(email: str) -> str:
    return hmac_sha256(ZK_AUTH_HMAC_KEY, email.lower().strip())


def encrypt_email(email: str) -> str:
    return json.dumps(encrypt_string(email.lower().strip(), ZK_AUTH_ENCRYPTION_KEY))


def decrypt_email(encrypted: str) -> str:
    return decrypt_string(json.loads(encrypted), ZK_AUTH_ENCRYPTION_KEY)


def generate_otp_code(length: int = 6) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def hash_otp_code(challenge_id: str, code: str) -> str:
    return hmac_sha256(ZK_AUTH_SESSION_SECRET, f"otp:{challenge_id}:{code}")


def create_opaque_token(byte_length: int = 32) -> str:
    return base64.urlsafe_b64encode(os.urandom(byte_length)).rstrip(b"=").decode("ascii")


def hash_session_token(token: str) -> str:
    return hmac_sha256(ZK_AUTH_SESSION_SECRET, f"session:{token}")


def hash_refresh_token(token: str) -> str:
    return hmac_sha256(ZK_AUTH_SESSION_SECRET, f"refresh:{token}")


def safe_equal(a: str, b: str) -> bool:
    return _hmac_mod.compare_digest(a.encode("utf8"), b.encode("utf8"))


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _zk_db_path() -> str:
    data_dir = os.environ.get("WORKFRAME_API_DATA_DIR", "/app/data")
    return os.path.join(data_dir, "zk_auth.db")


def _zk_db() -> sqlite3.Connection:
    db_path = _zk_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    # ponytail: DELETE only — WAL sidecars fail on Docker Desktop Windows bind mounts.
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA busy_timeout=30000")
    _zk_init_db(conn)
    return conn


def _zk_init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'suspended', 'deleted')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS identities (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type TEXT NOT NULL CHECK (type IN ('email', 'passkey', 'oauth')),
            identifier_hash TEXT NOT NULL,
            identifier_encrypted TEXT NOT NULL,
            verified_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (type, identifier_hash)
        );

        CREATE TABLE IF NOT EXISTS verification_challenges (
            id TEXT PRIMARY KEY,
            identity_type TEXT NOT NULL CHECK (identity_type IN ('email', 'phone')),
            identifier_hash TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            purpose TEXT NOT NULL CHECK (purpose IN ('login', 'signup', 'recovery')),
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            refresh_token_hash TEXT NOT NULL UNIQUE,
            token_family_id TEXT NOT NULL,
            user_agent_summary TEXT,
            ip_summary TEXT,
            created_at TEXT NOT NULL,
            last_seen_at TEXT,
            expires_at TEXT NOT NULL,
            revoked_at TEXT
        );

        CREATE TABLE IF NOT EXISTS profiles (
            user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            display_name TEXT,
            avatar_url TEXT,
            tagline TEXT,
            bio TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_identities_user_id ON identities(user_id);
        CREATE INDEX IF NOT EXISTS idx_identities_hash ON identities(type, identifier_hash);
        CREATE INDEX IF NOT EXISTS idx_challenges_hash ON verification_challenges(identity_type, identifier_hash, expires_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_family ON sessions(token_family_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_refresh ON sessions(refresh_token_hash);
    """)


# ---------------------------------------------------------------------------
# Auth service (ported from zk-auth/src/services/)
# ---------------------------------------------------------------------------

def start_email_verification(
    email: str,
    *,
    dev_local_unsafe: bool = False,
    expose_otp: bool = False,
) -> dict:
    normalized = email.lower().strip()
    identifier_hash = hash_email(normalized)
    challenge_id = str(uuid.uuid4())
    code = generate_otp_code()
    code_hash = hash_otp_code(challenge_id, code)
    now_ts = datetime.now(timezone.utc).isoformat()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)).isoformat()

    conn = _zk_db()
    try:
        conn.execute(
            "UPDATE verification_challenges SET used_at = ? WHERE identifier_hash = ? AND used_at IS NULL AND expires_at > ?",
            (now_ts, identifier_hash, now_ts),
        )
        conn.execute(
            """INSERT INTO verification_challenges
               (id, identity_type, identifier_hash, code_hash, purpose, max_attempts, expires_at, created_at)
               VALUES (?, 'email', ?, ?, 'login', ?, ?, ?)""",
            (challenge_id, identifier_hash, code_hash, OTP_MAX_ATTEMPTS, expires, now_ts),
        )
        conn.commit()
    finally:
        conn.close()

    result: dict = {"challenge_id": challenge_id}

    # Build verification URL
    import email_sender as email_mod
    from urllib.parse import urlencode
    verification_url = f"{email_mod.APP_BASE_URL}/?{urlencode({'email': normalized, 'code': code})}"

    email_sent = False
    email_error: str | None = None
    try:
        email_mod.send_verification_email(normalized, code, verification_url)
        email_sent = True
    except Exception as exc:
        email_error = str(exc)
        print(f"[zk-auth] Failed to send email: {exc}")

    result["email_sent"] = email_sent
    if email_error:
        result["email_error"] = email_error

    # ponytail: OTP in JSON only when DEV_LOCAL_UNSAFE and email did not go out, or explicit E2E install harness
    if expose_otp or (dev_local_unsafe and not email_sent):
        result["otp_code"] = code
        if dev_local_unsafe and not email_sent:
            result["_dev_warning"] = (
                "DEV_LOCAL_UNSAFE: OTP returned because email was not sent"
            )
        elif expose_otp:
            result["_e2e_warning"] = "WORKFRAME_E2E: OTP returned during install window"

    return result


def verify_email_code(email: str, code: str) -> dict:
    normalized = email.lower().strip()
    identifier_hash = hash_email(normalized)
    now_ts = datetime.now(timezone.utc).isoformat()

    conn = _zk_db()
    try:
        challenge = conn.execute(
            """SELECT * FROM verification_challenges
               WHERE identifier_hash = ? AND used_at IS NULL AND expires_at > ?
               ORDER BY created_at DESC LIMIT 1""",
            (identifier_hash, now_ts),
        ).fetchone()

        if not challenge:
            raise ValueError("Invalid or expired verification code.")

        if challenge["attempt_count"] >= challenge["max_attempts"]:
            raise ValueError("Invalid or expired verification code.")

        expected_hash = hash_otp_code(challenge["id"], code)
        if not safe_equal(expected_hash, challenge["code_hash"]):
            conn.execute(
                "UPDATE verification_challenges SET attempt_count = attempt_count + 1 WHERE id = ?",
                (challenge["id"],),
            )
            conn.commit()
            raise ValueError("Invalid or expired verification code.")

        conn.execute(
            "UPDATE verification_challenges SET used_at = ? WHERE id = ?",
            (now_ts, challenge["id"]),
        )

        identity = conn.execute(
            "SELECT * FROM identities WHERE type = 'email' AND identifier_hash = ?",
            (identifier_hash,),
        ).fetchone()

        is_new_user = False
        if not identity:
            user_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO users (id, status, created_at, updated_at) VALUES (?, 'active', ?, ?)",
                (user_id, now_ts, now_ts),
            )
            conn.execute(
                """INSERT INTO identities
                   (id, user_id, type, identifier_hash, identifier_encrypted, verified_at, created_at, updated_at)
                   VALUES (?, ?, 'email', ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), user_id, identifier_hash, encrypt_email(normalized), now_ts, now_ts, now_ts),
            )
            conn.execute(
                "INSERT INTO profiles (user_id, created_at, updated_at) VALUES (?, ?, ?)",
                (user_id, now_ts, now_ts),
            )
            is_new_user = True
        else:
            user_id = identity["user_id"]

        session_id = str(uuid.uuid4())
        refresh_token = create_opaque_token(32)
        refresh_token_hash = hash_refresh_token(refresh_token)
        token_family_id = str(uuid.uuid4())
        expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)).isoformat()

        conn.execute(
            """INSERT INTO sessions
               (id, user_id, refresh_token_hash, token_family_id, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, user_id, refresh_token_hash, token_family_id, now_ts, expires_at),
        )
        conn.commit()

        return {
            "user_id": user_id,
            "session_id": session_id,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "is_new_user": is_new_user,
        }
    except ValueError:
        raise
    except Exception as exc:
        conn.rollback()
        raise RuntimeError(f"Auth failed: {exc}") from exc
    finally:
        conn.close()


def create_session_for_email(email: str) -> dict:
    """Trusted invite path — session without OTP when invite token already proved mailbox."""
    normalized = email.lower().strip()
    identifier_hash = hash_email(normalized)
    now_ts = datetime.now(timezone.utc).isoformat()
    conn = _zk_db()
    try:
        identity = conn.execute(
            "SELECT * FROM identities WHERE type = 'email' AND identifier_hash = ?",
            (identifier_hash,),
        ).fetchone()
        is_new_user = False
        if not identity:
            user_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO users (id, status, created_at, updated_at) VALUES (?, 'active', ?, ?)",
                (user_id, now_ts, now_ts),
            )
            conn.execute(
                """INSERT INTO identities
                   (id, user_id, type, identifier_hash, identifier_encrypted, verified_at, created_at, updated_at)
                   VALUES (?, ?, 'email', ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), user_id, identifier_hash, encrypt_email(normalized), now_ts, now_ts, now_ts),
            )
            conn.execute(
                "INSERT INTO profiles (user_id, created_at, updated_at) VALUES (?, ?, ?)",
                (user_id, now_ts, now_ts),
            )
            is_new_user = True
        else:
            user_id = identity["user_id"]
        session_id = str(uuid.uuid4())
        refresh_token = create_opaque_token(32)
        refresh_token_hash = hash_refresh_token(refresh_token)
        token_family_id = str(uuid.uuid4())
        expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)).isoformat()
        conn.execute(
            """INSERT INTO sessions
               (id, user_id, refresh_token_hash, token_family_id, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, user_id, refresh_token_hash, token_family_id, now_ts, expires_at),
        )
        conn.commit()
        return {
            "user_id": user_id,
            "session_id": session_id,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "is_new_user": is_new_user,
        }
    except Exception as exc:
        conn.rollback()
        raise RuntimeError(f"Auth failed: {exc}") from exc
    finally:
        conn.close()


def logout_session(session_id: str) -> None:
    now_ts = datetime.now(timezone.utc).isoformat()
    conn = _zk_db()
    try:
        conn.execute("UPDATE sessions SET revoked_at = ? WHERE id = ?", (now_ts, session_id))
        conn.commit()
    finally:
        conn.close()


def refresh_session(refresh_token: str) -> dict:
    """Rotate a refresh token. Returns new session_id + refresh_token.

    Implements token family revocation: if a previously-used refresh token
    is replayed, the entire family is revoked (reuse detection).
    """
    token_hash = hash_refresh_token(refresh_token)
    now_ts = datetime.now(timezone.utc).isoformat()

    conn = _zk_db()
    try:
        session = conn.execute(
            "SELECT * FROM sessions WHERE refresh_token_hash = ?",
            (token_hash,),
        ).fetchone()

        if not session:
            # Possible token reuse — revoke the whole family
            # We can't look up by hash since the token is unknown, but we
            # can check if any session in a family has been revoked.
            # For now, just reject.
            raise ValueError("Invalid refresh token.")

        if session["revoked_at"] is not None:
            # Token reuse detected — revoke entire family
            conn.execute(
                "UPDATE sessions SET revoked_at = ? WHERE token_family_id = ?",
                (now_ts, session["token_family_id"]),
            )
            conn.commit()
            raise ValueError("Refresh token reuse detected. Session family revoked.")

        if session["expires_at"] < now_ts:
            raise ValueError("Refresh token expired.")

        # Rotate: new session ID + new refresh token, same family
        new_session_id = str(uuid.uuid4())
        new_refresh_token = create_opaque_token(32)
        new_refresh_hash = hash_refresh_token(new_refresh_token)
        new_expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)).isoformat()

        # Revoke old session
        conn.execute(
            "UPDATE sessions SET revoked_at = ? WHERE id = ?",
            (now_ts, session["id"]),
        )
        # Insert new session in same family
        conn.execute(
            """INSERT INTO sessions
               (id, user_id, refresh_token_hash, token_family_id, user_agent_summary, ip_summary, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (new_session_id, session["user_id"], new_refresh_hash,
             session["token_family_id"], session["user_agent_summary"],
             session["ip_summary"], now_ts, new_expires),
        )
        conn.commit()

        return {
            "user_id": session["user_id"],
            "session_id": new_session_id,
            "refresh_token": new_refresh_token,
            "expires_at": new_expires,
        }
    except ValueError:
        raise
    except Exception as exc:
        conn.rollback()
        raise RuntimeError(f"Refresh failed: {exc}") from exc
    finally:
        conn.close()


def validate_session_token(session_id: str) -> dict | None:
    now_ts = datetime.now(timezone.utc).isoformat()
    conn = _zk_db()
    try:
        session = conn.execute(
            """SELECT s.*, u.status as user_status
               FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.id = ? AND s.revoked_at IS NULL AND s.expires_at > ?""",
            (session_id, now_ts),
        ).fetchone()
        if not session or session["user_status"] != "active":
            return None
        conn.execute("UPDATE sessions SET last_seen_at = ? WHERE id = ?", (now_ts, session_id))
        conn.commit()
        return {"user_id": session["user_id"], "session_id": session["id"], "expires_at": session["expires_at"]}
    finally:
        conn.close()


def get_profile(user_id: str) -> dict | None:
    conn = _zk_db()
    try:
        row = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return None
        return {
            "user_id": row["user_id"],
            "display_name": row["display_name"],
            "avatar_url": row["avatar_url"],
            "tagline": row["tagline"],
            "bio": row["bio"],
        }
    finally:
        conn.close()


def update_profile(user_id: str, updates: dict) -> dict:
    allowed = {"display_name", "avatar_url", "tagline", "bio"}
    fields = {k: v for k, v in updates.items() if k in allowed and v is not None}
    if not fields:
        return get_profile(user_id)

    now_ts = datetime.now(timezone.utc).isoformat()
    fields["updated_at"] = now_ts

    conn = _zk_db()
    try:
        existing = conn.execute("SELECT 1 FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO profiles (user_id, created_at, updated_at) VALUES (?, ?, ?)",
                (user_id, now_ts, now_ts),
            )
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [user_id]
        conn.execute(f"UPDATE profiles SET {set_clause} WHERE user_id = ?", values)
        conn.commit()
    finally:
        conn.close()
    return get_profile(user_id)


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------

def session_cookie_name() -> str:
    # ponytail: WORKFRAME_INSTALL_ID scopes cookies per install; auth DB is per install (same email OK across installs).
    install_id = os.environ.get("WORKFRAME_INSTALL_ID", "").strip()
    if install_id:
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", install_id).strip("_")
        if safe:
            return f"{safe}_session"
    slug = re.sub(
        r"[^a-z0-9]+",
        "_",
        os.environ.get("WORKFRAME_PROJECT", "workframe").lower(),
    ).strip("_")
    return f"wf_{slug or 'workframe'}_session"


def session_cookie_value(session_id: str, ttl: int = None, secure: bool = True) -> str:
    if ttl is None:
        ttl = SESSION_TTL_DAYS * 86400
    name = session_cookie_name()
    val = f"{name}={session_id}; HttpOnly; SameSite=Lax; Path=/; Max-Age={ttl}"
    if secure:
        val += "; Secure"
    return val


def clear_session_cookie(secure: bool = True) -> str:
    name = session_cookie_name()
    val = f"{name}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"
    if secure:
        val += "; Secure"
    return val
