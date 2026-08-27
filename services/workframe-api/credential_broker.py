"""Provider-neutral credential broker — shared lease validation for internal proxies."""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any, Callable

import broker_audit
import internal_proxy_auth
import turn_credentials
import credential_vault

LEASE_PREFIX = turn_credentials.LEASE_PREFIX


def _oauth_bundle(secret: str) -> dict[str, Any] | None:
    try:
        value = json.loads(str(secret or ""))
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) and value.get("kind") == "oauth" else None


def materialize_provider_secret(provider: str, binding_id: str, secret: str) -> tuple[str, str]:
    """Return an outbound token while keeping OAuth bundles vault-only.

    The lease path is the only caller that receives the materialized token.
    Refresh is provider-neutral and opt-in: a bundle must provide its token
    endpoint and client id. Missing refresh metadata fails closed instead of
    falling back to runtime auth files.
    """
    bundle = _oauth_bundle(secret)
    if not bundle:
        return str(secret or ""), "ok" if str(secret or "").strip() else "missing"
    access = str(bundle.get("access_token") or "").strip()
    expires_at = float(bundle.get("expires_at") or 0)
    refresh = str(bundle.get("refresh_token") or "").strip()
    token_url = str(bundle.get("token_url") or "").strip()
    client_id = str(bundle.get("client_id") or "").strip()
    can_refresh = bool(refresh and token_url and client_id)
    known_fresh = bool(access and expires_at and expires_at > time.time() + 30)
    if known_fresh:
        return access, "ok"
    if not can_refresh:
        if access and not expires_at:
            return access, "ok"
        return "", "oauth_refresh_unavailable"
    form = {
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "client_id": client_id,
    }
    client_secret = str(bundle.get("client_secret") or "").strip()
    if client_secret:
        form["client_secret"] = client_secret
    req = urllib.request.Request(
        token_url,
        data=urllib.parse.urlencode(form).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return "", "oauth_refresh_failed"
    if not isinstance(payload, dict) or not str(payload.get("access_token") or "").strip():
        return "", "oauth_refresh_failed"
    new_bundle = dict(bundle)
    new_bundle["access_token"] = str(payload["access_token"])
    if payload.get("refresh_token"):
        new_bundle["refresh_token"] = str(payload["refresh_token"])
    if payload.get("expires_in"):
        new_bundle["expires_at"] = time.time() + float(payload["expires_in"])
    target_id = str(binding_id or "").strip()
    if target_id:
        operation_id = ""
        try:
            import credential_lifecycle

            metadata = credential_vault.read_secret_metadata(target_id)
            operation_id = credential_lifecycle.begin_operation(target_id, "refresh", state="rotating")
            credential_lifecycle.advance_generation(target_id, state="rotating")
            credential_vault.store_secret(
                target_id,
                json.dumps(new_bundle, sort_keys=True),
                env_var=metadata.get("env_var", ""),
                provider=metadata.get("provider") or provider,
                scope=metadata.get("scope") or "user",
                user_id=metadata.get("user_id", ""),
                workspace_id=metadata.get("workspace_id", ""),
            )
            credential_lifecycle.mark_active(target_id)
            credential_lifecycle.transition_operation(operation_id, "completed")
        except (OSError, RuntimeError, ValueError, sqlite3.Error):
            if operation_id:
                try:
                    credential_lifecycle.transition_operation(operation_id, "rotating", details={"reason": "refresh_persist_failed"})
                except Exception:
                    pass
            return "", "oauth_refresh_persist_failed"
    return str(new_bundle["access_token"]), "ok"


def extract_bearer(headers: dict[str, str]) -> str:
    auth = str(headers.get("Authorization") or headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    api_key = str(headers.get("X-Api-Key") or headers.get("x-api-key") or "").strip()
    if api_key:
        return api_key
    return ""


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


@dataclass(frozen=True)
class BrokerLeaseAuth:
    ok: bool
    lease: dict[str, Any] | None = None
    secret: str = ""
    env_var: str = ""
    status: int = 200
    error: str = ""
    deny_reason: str = ""
    credential_status: str = ""


def authorize_broker_lease(
    provider: str,
    headers: dict[str, str],
    *,
    resolve_secret: Callable[[str, str, str, str], tuple[str, str]],
    broker_kind: str = "",
    upstream_host: str = "",
) -> BrokerLeaseAuth:
    """Validate lease token, provider/profile binding, and vault secret for a broker hop."""
    provider = str(provider or "").strip().lower()
    host = str(upstream_host or "").strip().lower()
    kind = str(broker_kind or "").strip().lower()

    def _audit(auth: BrokerLeaseAuth, status: int) -> BrokerLeaseAuth:
        if kind:
            broker_audit.record_broker_event(
                broker_kind=kind,
                provider=provider,
                upstream_host=host,
                status=status,
                deny_reason=auth.deny_reason,
                lease=auth.lease,
            )
        return auth

    token = extract_bearer(headers)
    deny_reason, lease = turn_credentials.inspect_lease(token)
    if deny_reason:
        return _audit(
            BrokerLeaseAuth(
                ok=False,
                status=401,
                error="invalid lease",
                deny_reason=deny_reason,
                lease=lease,
            ),
            401,
        )
    if not lease:
        return _audit(
            BrokerLeaseAuth(
                ok=False,
                status=401,
                error="invalid lease",
                deny_reason="invalid_lease",
            ),
            401,
        )
    if str(lease.get("provider") or "").lower() != provider:
        return _audit(
            BrokerLeaseAuth(
                ok=False,
                status=403,
                error="provider mismatch",
                deny_reason="provider_mismatch",
                lease=lease,
            ),
            403,
        )

    ok_profile, profile_err, profile_status = validate_lease_profile(lease, headers)
    if not ok_profile:
        reason = "profile_header_required" if profile_status == 403 and "required" in profile_err else "profile_mismatch"
        return _audit(
            BrokerLeaseAuth(
                ok=False,
                status=profile_status,
                error=profile_err,
                deny_reason=reason,
                lease=lease,
            ),
            profile_status,
        )

    result_resolver = getattr(resolve_secret, "_typed_result_resolver", None)
    if result_resolver is None:
        # The API resolver is a module function; keep the compatibility path
        # for isolated callers and older tests.
        try:
            import credential_resolve

            if resolve_secret is credential_resolve._resolve_secret_for_lease:
                result_resolver = credential_resolve._resolve_secret_result_for_lease
        except ImportError:
            result_resolver = None
    if result_resolver is not None:
        env_var, read_result = turn_credentials.resolve_lease_secret_result(lease, result_resolver)
        secret = read_result.secret if read_result.ok else ""
        credential_status = read_result.status.value
    else:
        env_var, secret = turn_credentials.resolve_lease_secret(lease, resolve_secret)
        credential_status = (
            credential_vault.CredentialReadStatus.OK.value
            if secret
            else credential_vault.CredentialReadStatus.MISSING.value
        )
    secret, material_status = materialize_provider_secret(provider, str(lease.get("credential_binding_id") or ""), secret)
    if not secret:
        effective_status = material_status if material_status not in {"", "ok", "missing"} else credential_status
        return _audit(
            BrokerLeaseAuth(
                ok=False,
                status=402,
                error="oauth refresh unavailable" if material_status.startswith("oauth_") else "no credential",
                deny_reason=f"credential_{effective_status}",
                lease=lease,
                credential_status=effective_status,
            ),
            402,
        )
    return _audit(
        BrokerLeaseAuth(
            ok=True,
            lease=lease,
            secret=secret,
            env_var=env_var,
            credential_status=credential_status,
        ),
        200,
    )


def broker_error_body(auth: BrokerLeaseAuth) -> bytes:
    return json.dumps({"error": auth.error, "credential_status": auth.credential_status or None}).encode()


if __name__ == "__main__":
    assert extract_bearer({"Authorization": "Bearer wf_rt_abc"}) == "wf_rt_abc"
    assert extract_bearer({"X-Api-Key": "wf_rt_xyz"}) == "wf_rt_xyz"
    lease = {"profile_slug": "u-a-dev", "provider": "openrouter"}
    ok, err, code = validate_lease_profile(lease, {internal_proxy_auth.PROFILE_HEADER: "u-a-dev"})
    assert ok and not err and code == 0
    ok, err, code = validate_lease_profile(lease, {})
    assert not ok and code == 403
    print("credential_broker ok")
