"""Provider-neutral credential broker — shared lease validation for internal proxies."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

import broker_audit
import internal_proxy_auth
import turn_credentials

LEASE_PREFIX = turn_credentials.LEASE_PREFIX


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

    env_var, secret = turn_credentials.resolve_lease_secret(lease, resolve_secret)
    if not secret:
        return _audit(
            BrokerLeaseAuth(
                ok=False,
                status=402,
                error="no credential",
                deny_reason="no_credential",
                lease=lease,
            ),
            402,
        )
    return _audit(BrokerLeaseAuth(ok=True, lease=lease, secret=secret, env_var=env_var), 200)


def broker_error_body(auth: BrokerLeaseAuth) -> bytes:
    return json.dumps({"error": auth.error}).encode()


if __name__ == "__main__":
    assert extract_bearer({"Authorization": "Bearer wf_rt_abc"}) == "wf_rt_abc"
    assert extract_bearer({"X-Api-Key": "wf_rt_xyz"}) == "wf_rt_xyz"
    lease = {"profile_slug": "u-a-dev", "provider": "openrouter"}
    ok, err, code = validate_lease_profile(lease, {internal_proxy_auth.PROFILE_HEADER: "u-a-dev"})
    assert ok and not err and code == 0
    ok, err, code = validate_lease_profile(lease, {})
    assert not ok and code == 403
    print("credential_broker ok")
