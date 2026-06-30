"""Shared auth for /internal/llm and /internal/action — network + optional proxy token."""

from __future__ import annotations

import hmac
import ipaddress
import os
import secrets
from http.server import BaseHTTPRequestHandler
from pathlib import Path

PROXY_TOKEN_ENV = "WORKFRAME_PROXY_TOKEN"
PROXY_TOKEN_HEADER = "X-Workframe-Proxy-Token"
PROFILE_HEADER = "X-Workframe-Profile"
PROXY_TOKEN_FILE = ".proxy_token"
SHARED_PROXY_TOKEN_PATH = Path("/run/workframe-proxy/token")

_TOKEN: str | None = None
_TOKEN_PATH: Path | None = None


def _data_dir() -> Path:
    return Path(
        os.environ.get("WORKFRAME_API_DATA_DIR")
        or os.environ.get("MISSION_DATA_DIR")
        or Path(__file__).resolve().parent / "data"
    )


def _deployment_mode() -> str:
    return (os.environ.get("WORKFRAME_DEPLOYMENT_MODE") or "trusted_team").strip().lower()


def proxy_token_configured() -> bool:
    return bool(_loaded_proxy_token())


def _loaded_proxy_token() -> str:
    global _TOKEN, _TOKEN_PATH
    if _TOKEN is not None:
        return _TOKEN
    env = str(os.environ.get(PROXY_TOKEN_ENV) or "").strip()
    if env:
        _TOKEN = env
        return _TOKEN
    path = _data_dir() / PROXY_TOKEN_FILE
    _TOKEN_PATH = path
    if path.is_file():
        _TOKEN = path.read_text(encoding="utf-8").strip()
        return _TOKEN
    _TOKEN = ""
    return ""


def _sync_shared_proxy_token(token: str) -> None:
    value = str(token or "").strip()
    if not value:
        return
    try:
        SHARED_PROXY_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        SHARED_PROXY_TOKEN_PATH.write_text(value + "\n", encoding="utf-8")
    except OSError:
        pass


def bootstrap_proxy_token(*, allow_generate_file: bool = True) -> str:
    """Load proxy token from env or data dir; optionally create file for local dogfood."""
    global _TOKEN
    existing = str(os.environ.get(PROXY_TOKEN_ENV) or "").strip()
    if existing:
        _TOKEN = existing
        _sync_shared_proxy_token(existing)
        return existing
    path = _data_dir() / PROXY_TOKEN_FILE
    if path.is_file():
        _TOKEN = path.read_text(encoding="utf-8").strip()
        _sync_shared_proxy_token(_TOKEN)
        return _TOKEN
    if not allow_generate_file or _deployment_mode() == "public_multi_user":
        _TOKEN = ""
        return ""
    token = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n", encoding="utf-8")
    # ponytail: gateway reads same token from shared compose volume when env unset
    try:
        SHARED_PROXY_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        SHARED_PROXY_TOKEN_PATH.write_text(token + "\n", encoding="utf-8")
    except OSError:
        pass
    _TOKEN = token
    return token


def reset_proxy_token_for_tests() -> None:
    global _TOKEN, _TOKEN_PATH
    _TOKEN = None
    _TOKEN_PATH = None


def _client_ip(handler: BaseHTTPRequestHandler) -> str:
    return str(handler.client_address[0] if handler.client_address else "").strip()


def is_internal_client(host: str) -> bool:
    """Private/docker callers only — not routable public addresses."""
    addr = str(host or "").strip()
    if not addr:
        return False
    if addr in {"127.0.0.1", "::1", "localhost"}:
        return True
    try:
        ip = ipaddress.ip_address(addr.split("%", 1)[0])
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback


def _header_token(handler: BaseHTTPRequestHandler) -> str:
    return str(handler.headers.get(PROXY_TOKEN_HEADER) or "").strip()


def authorize_internal_proxy(handler: BaseHTTPRequestHandler) -> tuple[bool, str]:
    """Return (ok, error_code)."""
    if not is_internal_client(_client_ip(handler)):
        return False, "internal only"
    expected = _loaded_proxy_token()
    if not expected:
        return True, ""
    got = _header_token(handler)
    if not got or not hmac.compare_digest(got, expected):
        return False, "proxy token required"
    return True, ""


if __name__ == "__main__":
    reset_proxy_token_for_tests()
    os.environ[PROXY_TOKEN_ENV] = "test-proxy-token"
    assert proxy_token_configured()

    class _H:
        client_address = ("172.19.0.2", 1234)
        headers = {PROXY_TOKEN_HEADER: "test-proxy-token"}

    ok, err = authorize_internal_proxy(_H())  # type: ignore[arg-type]
    assert ok and not err
    _H.headers = {}
    ok, err = authorize_internal_proxy(_H())  # type: ignore[arg-type]
    assert not ok and err == "proxy token required"
    print("internal_proxy_auth ok")
