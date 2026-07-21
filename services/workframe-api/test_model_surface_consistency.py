#!/usr/bin/env python3
"""Regression tests for model save/provider surface (WF-034).

Run: python services/workframe-api/test_model_surface_consistency.py
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROF = "surface-test-agent"


def _run_checks(server) -> None:
    prof_dir = server._profile_dir(PROF)
    prof_dir.mkdir(parents=True, exist_ok=True)
    (prof_dir / "config.yaml").write_text(
        "model:\n  default: gpt-5.4-medium\n  provider: openai-codex\n",
        encoding="utf-8",
    )
    cfg_path = prof_dir / "config.yaml"
    before = cfg_path.read_bytes()

    # A: GET models must not mutate config.yaml
    server.hermes_models(PROF, user_id="", workspace_id="")
    assert cfg_path.read_bytes() == before, "hermes_models must not rewrite config on read"

    # B: reconcile idempotent when routing already matches codex oauth
    assert server._profile_routing_matches_billing(PROF, "codex")
    assert server._reconcile_profile_llm_for_user(PROF, "user-1", "") is False

    # C: billing resolution honors prefer= when model exists in that catalog
    connected = {"codex", "openrouter"}
    assert server._resolve_billing_provider_for_model(
        "gpt-5.4-medium", connected, prefer="codex",
    ) == "codex"
    assert server._resolve_billing_provider_for_model(
        "openrouter/owl-alpha", connected, prefer="openrouter",
    ) == "openrouter"
    assert server._resolve_billing_provider_for_model(
        "openai-codex/gpt-5.4-mini", {"codex", "openrouter"},
    ) == "codex"

    # D: set with explicit billing_provider returns billing id in response
    applied = server.hermes_model_set(
        PROF, "gpt-5.4-medium", user_id="", workspace_id="", billing_provider="codex",
    )
    assert applied.get("ok"), applied
    assert applied.get("billing_provider") == "codex"
    assert applied.get("provider") == "codex"

    # E: credential availability cannot silently change an agent-owned model/provider.
    (prof_dir / "config.yaml").write_text(
        "model:\n  default: openai-codex/gpt-5.4-mini\n  provider: custom\n"
        "  base_url: http://workframe-api:8080/internal/llm/openrouter/v1\n",
        encoding="utf-8",
    )
    _orig_picker = server._user_llm_providers_for_picker
    _orig_can = server._user_can_use_llm
    _orig_sync = server._sync_oauth_llm_to_profile
    _orig_reload = server._reload_runtime_profile_gateway
    server._user_llm_providers_for_picker = lambda uid: {"codex"} if uid == "user-1" else set()
    server._user_can_use_llm = lambda uid, ws, prov: uid == "user-1" and prov == "codex"
    server._sync_oauth_llm_to_profile = lambda *a, **k: None
    server._reload_runtime_profile_gateway = lambda *a, **k: None
    try:
        # Transport repair may add proxy-safe fallback rows, but it must not
        # switch the configured OpenRouter billing provider to Codex.
        assert server._reconcile_profile_llm_for_user(PROF, "user-1", "") is True
        block = server._read_model_block(PROF)
        assert block.get("provider") == "custom"
        assert block.get("default") == "openai-codex/gpt-5.4-mini"
        assert str(block.get("base_url") or "").endswith("/internal/llm/openrouter/v1")
    finally:
        server._user_llm_providers_for_picker = _orig_picker
        server._user_can_use_llm = _orig_can
        server._sync_oauth_llm_to_profile = _orig_sync
        server._reload_runtime_profile_gateway = _orig_reload

    # F: runtime disk wins over template in _read_model_block
    runtime_prof = "u-test-user-surface-test-agent"
    runtime_dir = server._profile_dir(runtime_prof)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "config.yaml").write_text(
        "model:\n  default: gpt-5.4-mini\n  provider: openai-codex\n",
        encoding="utf-8",
    )
    block = server._read_model_block(runtime_prof)
    assert block.get("default") == "gpt-5.4-mini", block
    assert block.get("provider") == "openai-codex", block
    assert server._resolve_models_profile(runtime_prof) == PROF

    # G: template model save mirrors to runtime (same model id, not stale template re-read)
    runtime_prof = "u-test-user2-surface-test-agent"
    runtime_dir = server._profile_dir(runtime_prof)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "config.yaml").write_text(
        "model:\n  default: gpt-5.4-medium\n  provider: openai-codex\n",
        encoding="utf-8",
    )
    _orig_restart = server._restart_runtime_profile_gateway
    server._restart_runtime_profile_gateway = lambda *a, **k: None
    try:
        applied = server.hermes_model_set(
            runtime_prof, "gpt-5.4-mini", user_id="test-user2", workspace_id="", billing_provider="codex",
        )
    finally:
        server._restart_runtime_profile_gateway = _orig_restart
    assert applied.get("ok"), applied
    assert applied.get("profile") == PROF, applied
    runtime_block = server._parse_model_block_from_disk(runtime_prof)
    assert runtime_block.get("default") == "gpt-5.4-mini", runtime_block
    template_block = server._parse_model_block_from_disk(PROF)
    assert template_block.get("default") == "gpt-5.4-mini", template_block
    assert template_block.get("provider") == "openai-codex", template_block

    # H: missing user credentials deny execution elsewhere; provider resolution
    # still reports the agent's configured Codex provider instead of OpenRouter.
    _orig_picker = server._user_llm_providers_for_picker
    _orig_can = server._user_can_use_llm
    server._user_llm_providers_for_picker = lambda _uid: {"openrouter"}
    server._user_can_use_llm = lambda *_args, **_kwargs: False
    try:
        assert server._llm_billing_provider(PROF, user_id="other-user") == "codex"
    finally:
        server._user_llm_providers_for_picker = _orig_picker
        server._user_can_use_llm = _orig_can

    # I: picker rows expose the billing provider encoded in the proxy URL,
    # never Hermes' internal ``custom`` transport label.
    proxy_block = {
        "default": "google/gemini-2.5-flash",
        "provider": "custom",
        "base_url": "http://workframe-api:8080/internal/llm/openrouter/v1",
        "fallback_chain": [
            {"provider": "custom", "model": "anthropic/claude-sonnet-4.5"},
        ],
    }
    augmented = server._augment_model_suggestions([], proxy_block)
    assert {row.get("billing_provider") for row in augmented} == {"openrouter"}, augmented
    assert augmented[0].get("label") == "gemini-2.5-flash", augmented
    normalized = server._normalized_profile_fallback_chain(proxy_block, "openrouter")
    assert normalized == [
        {"provider": "openrouter", "model": "anthropic/claude-sonnet-4.5"},
    ]


def _run_self_check() -> None:
    tmpdir = tempfile.mkdtemp(prefix="wf-model-surface-")
    os.environ["WORKFRAME_AGENTS_DIR"] = tmpdir
    os.environ["HERMES_DATA"] = tmpdir
    os.environ["WORKFRAME_API_DATA_DIR"] = str(Path(tmpdir) / "api")
    os.environ["WORKFRAME_PROJECT"] = "ModelSurfaceTest"
    os.environ["NATIVE_PROFILE"] = "surface-test-agent"

    spec = importlib.util.spec_from_file_location("wf_server_model_surface", ROOT / "server.py")
    server = importlib.util.module_from_spec(spec)
    sys.modules["wf_server_model_surface"] = server
    spec.loader.exec_module(server)
    prev_server = sys.modules.get("server")
    sys.modules["server"] = server  # ponytail: extracted modules resolve _srv() to this instance
    try:
        _run_checks(server)
    finally:
        if prev_server is None:
            sys.modules.pop("server", None)
        else:
            sys.modules["server"] = prev_server


if __name__ == "__main__":
    _run_self_check()
    print("model surface consistency self-check ok")
