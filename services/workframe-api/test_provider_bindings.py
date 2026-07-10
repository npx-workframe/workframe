"""WF-032 provider_bindings pure helpers self-check."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import provider_bindings  # noqa: E402


def test_hermes_oauth_auth_keys() -> None:
    keys = provider_bindings._hermes_oauth_auth_keys("openai-codex")
    assert "openai-codex" in keys
    assert "codex" in keys
    assert "openai_codex" in keys


def test_auth_json_has_oauth_material() -> None:
    pool_only = {
        "version": 1,
        "providers": {},
        "credential_pool": {"openai-codex": [{"id": "x", "auth_type": "oauth"}]},
    }
    assert provider_bindings._auth_json_has_oauth_material(pool_only)


def test_merge_oauth_auth_into_profile() -> None:
    pool_only = {
        "version": 1,
        "providers": {},
        "credential_pool": {"openai-codex": [{"id": "x", "auth_type": "oauth"}]},
    }
    merged: dict = {"version": 1, "providers": {}, "credential_pool": {}}
    assert provider_bindings._merge_oauth_auth_into_profile(merged, pool_only, "openai-codex")
    assert merged["credential_pool"].get("openai-codex")


def test_parse_device_oauth_log() -> None:
    text = "Open this URL\n  https://auth.openai.com/device\nEnter this code\n  ABCD-1234"
    parsed = provider_bindings._parse_device_oauth_log(text)
    assert parsed["verification_uri"] and "openai.com" in parsed["verification_uri"]
    assert parsed["user_code"] == "ABCD-1234"


def test_device_oauth_error_from_log() -> None:
    text = (
        "hermes_cli.auth.AuthError: OpenAI is rate-limiting Codex login requests (HTTP 429). "
        "Wait a minute and run the login again."
    )
    msg = provider_bindings._device_oauth_error_from_log(text)
    assert msg and "429" in msg


if __name__ == "__main__":
    test_hermes_oauth_auth_keys()
    test_auth_json_has_oauth_material()
    test_merge_oauth_auth_into_profile()
    test_parse_device_oauth_log()
    test_device_oauth_error_from_log()
    print("test_provider_bindings: ok")
