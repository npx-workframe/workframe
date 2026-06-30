"""Minimal OIDC id_token verification (RS256 + JWKS) — no extra dependencies."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

_JWKS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_JWKS_TTL = 3600.0


def _b64url_decode(raw: str) -> bytes:
    padded = raw + "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _jwk_to_rsa(key: dict[str, Any]) -> RSAPublicKey:
    n = int.from_bytes(_b64url_decode(str(key["n"])), "big")
    e = int.from_bytes(_b64url_decode(str(key["e"])), "big")
    return rsa.RSAPublicNumbers(e, n).public_key()


def _fetch_jwks(jwks_url: str) -> dict[str, Any]:
    now = time.time()
    cached = _JWKS_CACHE.get(jwks_url)
    if cached and cached[0] > now:
        return cached[1]
    req = urllib.request.Request(jwks_url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("invalid jwks")
    _JWKS_CACHE[jwks_url] = (now + _JWKS_TTL, payload)
    return payload


def verify_rs256_id_token(
    token: str,
    *,
    audience: str,
    issuer: str | tuple[str, ...] = (),
    jwks_url: str,
    clock_skew: int = 60,
) -> dict[str, Any]:
    parts = str(token or "").split(".")
    if len(parts) != 3:
        raise ValueError("invalid id_token")
    header = json.loads(_b64url_decode(parts[0]))
    payload = json.loads(_b64url_decode(parts[1]))
    if str(header.get("alg") or "") != "RS256":
        raise ValueError("unsupported jwt alg")
    kid = str(header.get("kid") or "")
    jwks = _fetch_jwks(jwks_url)
    keys = jwks.get("keys") if isinstance(jwks.get("keys"), list) else []
    pub: RSAPublicKey | None = None
    for entry in keys:
        if not isinstance(entry, dict):
            continue
        if kid and str(entry.get("kid") or "") != kid:
            continue
        if str(entry.get("kty") or "") != "RSA":
            continue
        pub = _jwk_to_rsa(entry)
        break
    if pub is None:
        raise ValueError("jwks key not found")
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    signature = _b64url_decode(parts[2])
    pub.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())

    now = int(time.time())
    exp = int(payload.get("exp") or 0)
    if exp and now > exp + clock_skew:
        raise ValueError("id_token expired")
    iat = int(payload.get("iat") or 0)
    if iat and now + clock_skew < iat:
        raise ValueError("id_token not yet valid")

    iss = str(payload.get("iss") or "")
    allowed_iss = issuer or ()
    if allowed_iss and iss not in allowed_iss:
        raise ValueError("issuer mismatch")

    aud = payload.get("aud")
    aud_ok = audience in (aud if isinstance(aud, list) else [aud])
    if not aud_ok:
        raise ValueError("audience mismatch")

    if not isinstance(payload, dict):
        raise ValueError("invalid claims")
    return payload


def verify_google_id_token(token: str, client_id: str) -> dict[str, Any]:
    return verify_rs256_id_token(
        token,
        audience=str(client_id or "").strip(),
        issuer=("https://accounts.google.com", "accounts.google.com"),
        jwks_url="https://www.googleapis.com/oauth2/v3/certs",
    )
