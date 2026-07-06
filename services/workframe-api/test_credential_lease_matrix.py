"""WF-028 lease validation test matrix — expired, revoked, mismatch, proxy token.

Run: python services/workframe-api/test_credential_lease_matrix.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import broker_audit
import credential_broker
import internal_proxy_auth
import turn_credentials
from internal_proxy_auth import PROFILE_HEADER, PROXY_TOKEN_ENV, reset_proxy_token_for_tests

_TD = tempfile.mkdtemp(prefix="wf-lease-matrix-")
os.environ["WORKFRAME_API_DATA_DIR"] = _TD
turn_credentials.WORKFRAME_DB = Path(_TD) / "workframe.db"
turn_credentials._SCHEMA_READY.clear()
broker_audit.WORKFRAME_DB = Path(_TD) / "workframe.db"
broker_audit._SCHEMA_READY.clear()


def _resolve_secret(_user: str, _ws: str, _provider: str, _binding: str) -> tuple[str, str]:
    return "OPENROUTER_API_KEY", "sk-test-secret"


def _issue(**kwargs: str) -> str:
    return turn_credentials.issue_lease(
        kwargs.get("run_id", "run-test"),
        kwargs.get("user", "user-a"),
        kwargs.get("workspace", "ws-1"),
        kwargs.get("provider", "openrouter"),
        kwargs.get("profile", "u-user-a-dev"),
        kwargs.get("binding", "bind-1"),
    )


def _headers(token: str, profile: str = "u-user-a-dev") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        PROFILE_HEADER: profile,
    }


def test_active_lease_ok() -> None:
    tok = _issue(run_id="run-ok")
    auth = credential_broker.authorize_broker_lease(
        "openrouter",
        _headers(tok),
        resolve_secret=_resolve_secret,
    )
    assert auth.ok and auth.secret == "sk-test-secret"


def test_revoked_lease() -> None:
    tok = _issue(run_id="run-revoked")
    turn_credentials.revoke_lease("run-revoked")
    reason, _ = turn_credentials.inspect_lease(tok)
    assert reason == "revoked"
    auth = credential_broker.authorize_broker_lease(
        "openrouter",
        _headers(tok),
        resolve_secret=_resolve_secret,
    )
    assert not auth.ok and auth.deny_reason == "revoked" and auth.status == 401


def test_expired_lease() -> None:
    tok = _issue(run_id="run-expired")
    past = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    conn = sqlite3.connect(str(turn_credentials.WORKFRAME_DB))
    conn.execute(
        "UPDATE turn_credential_leases SET expires_at = ? WHERE run_id = ?",
        (past, "run-expired"),
    )
    conn.commit()
    conn.close()
    reason, _ = turn_credentials.inspect_lease(tok)
    assert reason == "expired"
    auth = credential_broker.authorize_broker_lease(
        "openrouter",
        _headers(tok),
        resolve_secret=_resolve_secret,
    )
    assert not auth.ok and auth.deny_reason == "expired"


def test_provider_mismatch() -> None:
    tok = _issue(run_id="run-prov", provider="openrouter")
    auth = credential_broker.authorize_broker_lease(
        "anthropic",
        _headers(tok),
        resolve_secret=_resolve_secret,
    )
    assert not auth.ok and auth.deny_reason == "provider_mismatch" and auth.status == 403


def test_profile_mismatch() -> None:
    tok = _issue(run_id="run-prof", profile="u-user-a-dev")
    auth = credential_broker.authorize_broker_lease(
        "openrouter",
        _headers(tok, profile="u-other-dev"),
        resolve_secret=_resolve_secret,
    )
    assert not auth.ok and auth.deny_reason == "profile_mismatch" and auth.status == 403


def test_missing_profile_header() -> None:
    tok = _issue(run_id="run-noprof", profile="u-user-a-dev")
    auth = credential_broker.authorize_broker_lease(
        "openrouter",
        {"Authorization": f"Bearer {tok}"},
        resolve_secret=_resolve_secret,
    )
    assert not auth.ok and auth.deny_reason == "profile_header_required"


def test_missing_proxy_token() -> None:
    reset_proxy_token_for_tests()
    os.environ[PROXY_TOKEN_ENV] = "matrix-proxy-token"

    class _Handler:
        client_address = ("172.19.0.2", 1234)
        headers: dict[str, str] = {}

    ok, err = internal_proxy_auth.authorize_internal_proxy(_Handler())  # type: ignore[arg-type]
    assert not ok and err == "proxy token required"

    _Handler.headers = {internal_proxy_auth.PROXY_TOKEN_HEADER: "matrix-proxy-token"}
    ok, err = internal_proxy_auth.authorize_internal_proxy(_Handler())  # type: ignore[arg-type]
    assert ok and not err


def test_broker_audit_on_deny() -> None:
    broker_audit._SCHEMA_READY.clear()
    tok = _issue(run_id="run-audit")
    turn_credentials.revoke_lease("run-audit")
    credential_broker.authorize_broker_lease(
        "openrouter",
        _headers(tok),
        resolve_secret=_resolve_secret,
        broker_kind="llm",
        upstream_host="openrouter.ai",
    )
    events = broker_audit.list_broker_events(limit=20)
    denied = [e for e in events if e.get("deny_reason") == "revoked" and e.get("run_id") == "run-audit"]
    assert denied


def main() -> None:
    test_active_lease_ok()
    test_revoked_lease()
    test_expired_lease()
    test_provider_mismatch()
    test_profile_mismatch()
    test_missing_profile_header()
    test_missing_proxy_token()
    test_broker_audit_on_deny()
    print("credential lease matrix ok")


if __name__ == "__main__":
    main()
