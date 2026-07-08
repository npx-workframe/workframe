"""WF-032 extract: ensure profile Hermes API is up (start/restart lifecycle)."""

from __future__ import annotations

from typing import Any

import profile_gateway


def _srv():
    import server as srv

    return srv


def ensure_profile_api(
    profile: str,
    user_id: str = "",
    workspace_id: str = "",
    *,
    bootstrap_providers: bool = True,
) -> dict[str, Any]:
    """Start profile gateway if down. ponytail: bind/chat must not mutate yaml or bootstrap creds."""
    prof = _srv().resolve_hermes_profile(profile)
    port = profile_gateway._profile_api_port(prof)
    if profile_gateway._profile_api_healthy(prof):
        return {"ok": True, "profile": prof, "api_port": port, "started": False}
    # ponytail: gateway restart (~7s) before supervisor cold start (~37s).
    if (
        _srv()._is_runtime_profile_slug(prof)
        and prof != _srv()._primary_profile()
        and _srv()._runtime_profile_on_disk(prof)
    ):
        with _srv()._gateway_lifecycle_lock:
            if profile_gateway._profile_api_healthy(prof, use_cache=False):
                return {"ok": True, "profile": prof, "api_port": port, "started": False}
            code, _out = _srv()._gateway_exec(prof, ["gateway", "restart"])
            if code == 0:
                _srv()._invalidate_profile_health_cache(prof)
                if profile_gateway._wait_profile_api_healthy(prof, attempts=48, delay=0.25):
                    return {"ok": True, "profile": prof, "api_port": port, "started": False}
    if prof == _srv()._primary_profile():
        ok, out, _port = profile_gateway._configure_profile_api(prof)
        if not ok:
            raise ValueError(f"profile api config failed: {out}")
        _srv()._restart_stack_gateway()
        if not profile_gateway._wait_profile_api_healthy(prof):
            raise ValueError(f"profile api did not become healthy: {prof}")
        return {"ok": True, "profile": prof, "api_port": port, "started": True}
    if bootstrap_providers and user_id:
        _srv()._bootstrap_profile_providers(prof, user_id, workspace_id)
    with _srv()._gateway_lifecycle_lock:
        if profile_gateway._profile_api_healthy(prof):
            return {"ok": True, "profile": prof, "api_port": port, "started": False}
        result = profile_gateway.profile_gateway_lifecycle(
            prof, "start", bootstrap_providers=bootstrap_providers
        )
        if not profile_gateway._wait_profile_api_healthy(prof):
            raise ValueError(f"profile api did not become healthy: {prof}")
        return {
            **result,
            "ok": True,
            "profile": prof,
            "api_port": port,
            "started": True,
        }
