"""Provider/model routing repairs for vault-backed API-key providers."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest
import yaml

API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import server  # noqa: E402


@pytest.fixture()
def routing_data_dir():
    with tempfile.TemporaryDirectory(prefix="wf-routing-") as tmp:
        yield Path(tmp)


def test_native_openrouter_config_is_reconciled_to_internal_proxy(
    monkeypatch: pytest.MonkeyPatch,
    routing_data_dir: Path,
) -> None:
    tmp_path = routing_data_dir
    profile = "dogfood-agent"
    profile_dir = tmp_path / "profiles" / profile
    profile_dir.mkdir(parents=True)
    config_path = profile_dir / "config.yaml"
    config_path.write_text(
        "model:\n"
        "  default: google/gemini-2.5-flash\n"
        "  provider: openrouter\n"
        "  base_url: https://openrouter.ai/api/v1\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(server, "HERMES_DATA", tmp_path)
    monkeypatch.setattr(server, "NATIVE_PROFILE", profile)
    monkeypatch.setattr(server, "WORKFRAME_LLM_PROXY_INTERNAL", "http://workframe-api:8000")
    monkeypatch.setattr(server, "_user_llm_providers_for_picker", lambda _user: {"openrouter"})
    monkeypatch.setattr(server, "_user_can_use_llm", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(server, "_reload_runtime_profile_gateway", lambda *_args, **_kwargs: None)

    assert server._reconcile_profile_llm_for_user(profile, "user-1", "workspace-1") is True

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert cfg["model"]["default"] == "google/gemini-2.5-flash"
    assert cfg["model"]["provider"] == "custom"
    assert cfg["model"]["base_url"] == "http://workframe-api:8000/internal/llm/openrouter/v1"
    assert isinstance(cfg["fallback_providers"], list)
    assert cfg["fallback_providers"]
    assert all(entry["provider"] == "custom" for entry in cfg["fallback_providers"])


def test_native_openrouter_reconcile_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    routing_data_dir: Path,
) -> None:
    tmp_path = routing_data_dir
    profile = "dogfood-agent"
    profile_dir = tmp_path / "profiles" / profile
    profile_dir.mkdir(parents=True)
    config_path = profile_dir / "config.yaml"
    config_path.write_text(
        "model:\n"
        "  default: google/gemini-2.5-flash\n"
        "  provider: custom\n"
        "  base_url: http://workframe-api:8000/internal/llm/openrouter/v1\n"
        "fallback_providers:\n"
        "  - provider: custom\n"
        "    model: meta-llama/llama-3.3-70b-instruct:free\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(server, "HERMES_DATA", tmp_path)
    monkeypatch.setattr(server, "NATIVE_PROFILE", profile)
    monkeypatch.setattr(server, "WORKFRAME_LLM_PROXY_INTERNAL", "http://workframe-api:8000")
    monkeypatch.setattr(server, "_user_llm_providers_for_picker", lambda _user: {"openrouter"})
    monkeypatch.setattr(server, "_user_can_use_llm", lambda *_args, **_kwargs: True)

    assert server._reconcile_profile_llm_for_user(profile, "user-1", "workspace-1") is False


def test_openrouter_reconcile_accepts_pyyaml_indentless_fallback_sequence(
    monkeypatch: pytest.MonkeyPatch,
    routing_data_dir: Path,
) -> None:
    profile = "dogfood-agent"
    profile_dir = routing_data_dir / "profiles" / profile
    profile_dir.mkdir(parents=True)
    config_path = profile_dir / "config.yaml"
    config_path.write_text(
        "model:\n"
        "  default: openrouter/auto\n"
        "  provider: custom\n"
        "  base_url: http://workframe-api:8000/internal/llm/openrouter/v1\n"
        "fallback_providers:\n"
        "- provider: custom\n"
        "  model: anthropic/claude-sonnet-4.5\n"
        "- provider: custom\n"
        "  model: meta-llama/llama-3.3-70b-instruct:free\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(server, "HERMES_DATA", routing_data_dir)
    monkeypatch.setattr(server, "NATIVE_PROFILE", profile)
    monkeypatch.setattr(server, "WORKFRAME_LLM_PROXY_INTERNAL", "http://workframe-api:8000")
    monkeypatch.setattr(server, "_user_llm_providers_for_picker", lambda _user: {"openrouter"})
    monkeypatch.setattr(server, "_user_can_use_llm", lambda *_args, **_kwargs: True)

    block = server._read_model_block(profile)
    assert block["fallback_chain"] == [
        {"provider": "custom", "model": "anthropic/claude-sonnet-4.5"},
        {"provider": "custom", "model": "meta-llama/llama-3.3-70b-instruct:free"},
    ]
    assert server._profile_llm_proxy_ready(profile, "openrouter") is True
    assert server._reconcile_profile_llm_for_user(profile, "user-1", "workspace-1") is False
