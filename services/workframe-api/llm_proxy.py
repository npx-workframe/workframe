"""Internal LLM proxy — Hermes sends lease tokens; API vault supplies upstream keys."""

from __future__ import annotations

import json
import os
import re
import socket
import ssl
import urllib.error
import urllib.request
from typing import Any, Callable
from http.server import BaseHTTPRequestHandler

import internal_proxy_auth
import turn_credentials

LEASE_PREFIX = turn_credentials.LEASE_PREFIX

UPSTREAM_BASE: dict[str, str] = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "google": "https://generativelanguage.googleapis.com/v1beta",
    "deepseek": "https://api.deepseek.com/v1",
}

PROXY_PATH_RE = re.compile(r"^/internal/llm/([a-z0-9_-]+)(/.*)?$", re.IGNORECASE)


def normalize_upstream_path(base: str, subpath: str) -> str:
    """Drop a leading /v1 when upstream base already ends with /v1.

    Hermes uses model.base_url …/internal/llm/openrouter/v1; the OpenAI client
    then requests …/v1/chat/completions, which we forward as subpath /v1/….
    """
    path = subpath if str(subpath or "").startswith("/") else f"/{subpath or ''}"
    base_norm = str(base or "").rstrip("/")
    if path == "/v1":
        return ""
    if path.startswith("/v1/") and base_norm.endswith("/v1"):
        return path[3:]
    return path


def is_internal_client(host: str) -> bool:
    """Allow docker/private callers only — not public browser origins."""
    return internal_proxy_auth.is_internal_client(host)


def authorize_internal_proxy(handler: BaseHTTPRequestHandler) -> tuple[bool, str]:
    return internal_proxy_auth.authorize_internal_proxy(handler)


def extract_profile_slug(headers: dict[str, str]) -> str:
    return str(
        headers.get(internal_proxy_auth.PROFILE_HEADER)
        or headers.get("x-workframe-profile")
        or ""
    ).strip()


def validate_lease_profile(
    lease: dict[str, Any],
    headers: dict[str, str],
) -> tuple[bool, str, int]:
    """Bind bearer lease to calling Hermes profile (0022 N2 / 0023 C1)."""
    want = str(lease.get("profile_slug") or "").strip()
    if not want:
        return True, "", 0
    got = extract_profile_slug(headers)
    if not got:
        return False, "profile header required", 403
    if got != want:
        return False, "profile mismatch", 403
    return True, "", 0


def extract_bearer(headers: dict[str, str]) -> str:
    auth = str(headers.get("Authorization") or headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    api_key = str(headers.get("X-Api-Key") or headers.get("x-api-key") or "").strip()
    if api_key:
        return api_key
    return ""


def upstream_auth_header(provider: str, secret: str) -> dict[str, str]:
    provider = str(provider or "").strip().lower()
    secret = str(secret or "").strip()
    if provider == "anthropic":
        return {"x-api-key": secret, "anthropic-version": "2023-06-01"}
    if provider == "google":
        return {"x-goog-api-key": secret}
    return {"Authorization": f"Bearer {secret}"}


def _error_response(status: int, error: str) -> tuple[int, dict[str, str], bytes]:
    return status, {"Content-Type": "application/json"}, json.dumps({"error": error}).encode()


def _build_upstream_request(
    provider: str,
    subpath: str,
    method: str,
    headers: dict[str, str],
    body: bytes | None,
    *,
    resolve_secret: Callable[[str, str, str, str], tuple[str, str]],
) -> tuple[urllib.request.Request | None, tuple[int, dict[str, str], bytes] | None]:
    provider = str(provider or "").strip().lower()
    base = UPSTREAM_BASE.get(provider)
    if not base:
        return None, _error_response(404, "unknown provider")

    token = extract_bearer(headers)
    lease = turn_credentials.validate_lease(token)
    if not lease:
        return None, _error_response(401, "invalid lease")
    if str(lease.get("provider") or "").lower() != provider:
        return None, _error_response(403, "provider mismatch")

    ok_profile, profile_err, profile_status = validate_lease_profile(lease, headers)
    if not ok_profile:
        return None, _error_response(profile_status, profile_err)

    _env_var, secret = turn_credentials.resolve_lease_secret(lease, resolve_secret)
    if not secret:
        return None, _error_response(402, "no credential")

    path = normalize_upstream_path(base, subpath)
    url = f"{base.rstrip('/')}{path}"
    upstream_headers = {
        k: v
        for k, v in headers.items()
        if k.lower() not in {
            "host",
            "connection",
            "content-length",
            "authorization",
            "x-api-key",
            "x-goog-api-key",
        }
    }
    upstream_headers.update(upstream_auth_header(provider, secret))
    if provider == "openrouter":
        upstream_headers.setdefault("HTTP-Referer", "https://workfra.me")
        upstream_headers.setdefault("X-Title", "Workframe")

    req = urllib.request.Request(url, data=body, headers=upstream_headers, method=method.upper())
    return req, None


def forward_request(
    provider: str,
    subpath: str,
    method: str,
    headers: dict[str, str],
    body: bytes | None,
    *,
    resolve_secret: Callable[[str, str, str, str], tuple[str, str]],
) -> tuple[int, dict[str, str], bytes]:
    req, error = _build_upstream_request(
        provider,
        subpath,
        method,
        headers,
        body,
        resolve_secret=resolve_secret,
    )
    if error:
        return error
    assert req is not None
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            resp_body = resp.read()
            out_headers = {"Content-Type": resp.headers.get("Content-Type", "application/octet-stream")}
            return resp.status, out_headers, resp_body
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        out_headers = {"Content-Type": exc.headers.get("Content-Type", "application/json")}
        return exc.code, out_headers, raw


def stream_request_to_handler(
    handler: BaseHTTPRequestHandler,
    provider: str,
    subpath: str,
    method: str,
    headers: dict[str, str],
    body: bytes | None,
    *,
    resolve_secret: Callable[[str, str, str, str], tuple[str, str]],
) -> None:
    req, error = _build_upstream_request(
        provider,
        subpath,
        method,
        headers,
        body,
        resolve_secret=resolve_secret,
    )
    if error:
        status, out_headers, resp_body = error
        handler.send_response(status)
        for key, value in out_headers.items():
            handler.send_header(key, value)
        handler.end_headers()
        handler.wfile.write(resp_body)
        return

    assert req is not None
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            handler.send_response(resp.status)
            handler.send_header("Content-Type", content_type)
            handler.end_headers()
            if "text/event-stream" in content_type.lower():
                while True:
                    line = resp.readline()
                    if not line:
                        break
                    handler.wfile.write(line)
                    handler.wfile.flush()
            else:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    handler.wfile.write(chunk)
                    handler.wfile.flush()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        handler.send_response(exc.code)
        handler.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
        handler.end_headers()
        handler.wfile.write(raw)
    except urllib.error.URLError as exc:
        handler.send_response(502)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"error": f"upstream unavailable: {exc}"}).encode())


def handle_proxy_request(
    handler: BaseHTTPRequestHandler,
    path: str,
    method: str,
    body: bytes | None,
    *,
    resolve_secret: Callable[[str, str, str, str], tuple[str, str]],
) -> bool:
    """Return True if handled."""
    ok, err = authorize_internal_proxy(handler)
    if not ok:
        handler.send_response(403)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"error": err}).encode())
        return True

    match = PROXY_PATH_RE.match(path)
    if not match:
        return False

    provider = match.group(1).lower()
    subpath = match.group(2) or "/"
    headers = {k: v for k, v in handler.headers.items()}
    stream_request_to_handler(
        handler,
        provider,
        subpath,
        method,
        headers,
        body,
        resolve_secret=resolve_secret,
    )
    return True
