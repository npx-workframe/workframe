from __future__ import annotations

import profile_gateway


def test_wait_profile_api_health_bypasses_negative_cache(monkeypatch) -> None:
    server = profile_gateway._srv()
    monkeypatch.setattr(server, "resolve_hermes_profile", lambda profile: profile)
    monkeypatch.setattr(profile_gateway.time, "sleep", lambda _delay: None)

    cache_modes: list[bool] = []

    def health(_profile: str, **kwargs) -> bool:
        cache_modes.append(bool(kwargs.get("use_cache", True)))
        return len(cache_modes) >= 3

    monkeypatch.setattr(profile_gateway, "_profile_api_healthy", health)

    assert profile_gateway._wait_profile_api_healthy("dogfood-agent", attempts=4, delay=0.01)
    assert cache_modes == [False, False, False]


def test_wait_profile_api_health_stops_after_requested_attempts(monkeypatch) -> None:
    server = profile_gateway._srv()
    monkeypatch.setattr(server, "resolve_hermes_profile", lambda profile: profile)
    sleeps: list[float] = []
    monkeypatch.setattr(profile_gateway.time, "sleep", sleeps.append)
    monkeypatch.setattr(
        profile_gateway,
        "_profile_api_healthy",
        lambda _profile, **kwargs: False,
    )

    assert not profile_gateway._wait_profile_api_healthy(
        "dogfood-agent", attempts=3, delay=0.25,
    )
    assert sleeps == [0.25, 0.25, 0.25]
