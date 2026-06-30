"""Internal action proxy — dev/tool PATs stay in vault; Hermes sends lease tokens."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler
from typing import Any, Callable

import llm_proxy
import turn_credentials

UPSTREAM_BASE: dict[str, str] = {
    "github": "https://api.github.com",
    "vercel": "https://api.vercel.com",
    "netlify": "https://api.netlify.com/api/v1",
}

PROXY_PATH_RE = re.compile(r"^/internal/action/([a-z0-9_-]+)(/.*)?$", re.IGNORECASE)


def upstream_auth_header(provider: str, secret: str) -> dict[str, str]:
    provider = str(provider or "").strip().lower()
    secret = str(secret or "").strip()
    if provider == "github":
        return {"Authorization": f"Bearer {secret}", "Accept": "application/vnd.github+json"}
    if provider == "netlify":
        return {"Authorization": f"Bearer {secret}"}
    return {"Authorization": f"Bearer {secret}"}


def forward_request(
    provider: str,
    subpath: str,
    method: str,
    headers: dict[str, str],
    body: bytes | None,
    *,
    resolve_secret: Callable[[str, str, str, str], tuple[str, str]],
) -> tuple[int, dict[str, str], bytes]:
    provider = str(provider or "").strip().lower()
    base = UPSTREAM_BASE.get(provider)
    if not base:
        return 404, {"Content-Type": "application/json"}, json.dumps({"error": "unknown provider"}).encode()

    token = llm_proxy.extract_bearer(headers)
    lease = turn_credentials.validate_lease(token)
    if not lease:
        return 401, {"Content-Type": "application/json"}, json.dumps({"error": "invalid lease"}).encode()
    if str(lease.get("provider") or "").lower() != provider:
        return 403, {"Content-Type": "application/json"}, json.dumps({"error": "provider mismatch"}).encode()

    ok_profile, profile_err, profile_status = llm_proxy.validate_lease_profile(lease, headers)
    if not ok_profile:
        return (
            profile_status,
            {"Content-Type": "application/json"},
            json.dumps({"error": profile_err}).encode(),
        )

    _env_var, secret = turn_credentials.resolve_lease_secret(lease, resolve_secret)
    if not secret:
        return 402, {"Content-Type": "application/json"}, json.dumps({"error": "no credential"}).encode()

    path = subpath if subpath.startswith("/") else f"/{subpath}"
    url = f"{base.rstrip('/')}{path}"
    upstream_headers = {
        k: v
        for k, v in headers.items()
        if k.lower()
        not in {
            "host",
            "connection",
            "content-length",
            "authorization",
            "x-api-key",
        }
    }
    upstream_headers.update(upstream_auth_header(provider, secret))

    req = urllib.request.Request(url, data=body, headers=upstream_headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            resp_body = resp.read()
            out_headers = {"Content-Type": resp.headers.get("Content-Type", "application/octet-stream")}
            return resp.status, out_headers, resp_body
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        out_headers = {"Content-Type": exc.headers.get("Content-Type", "application/json")}
        return exc.code, out_headers, raw


def handle_proxy_request(
    handler: BaseHTTPRequestHandler,
    path: str,
    method: str,
    body: bytes | None,
    *,
    resolve_secret: Callable[[str, str, str, str], tuple[str, str]],
) -> bool:
    ok, err = llm_proxy.authorize_internal_proxy(handler)
    if not ok:
        handler.send_response(403)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"error": err or "internal only"}).encode())
        return True

    match = PROXY_PATH_RE.match(path)
    if not match:
        return False

    provider = match.group(1).lower()
    subpath = match.group(2) or "/"
    headers = {k: v for k, v in handler.headers.items()}
    status, out_headers, resp_body = forward_request(
        provider,
        subpath,
        method,
        headers,
        body,
        resolve_secret=resolve_secret,
    )
    handler.send_response(status)
    for key, value in out_headers.items():
        handler.send_header(key, value)
    handler.end_headers()
    handler.wfile.write(resp_body)
    return True
