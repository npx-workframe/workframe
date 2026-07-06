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
tmpdir = tempfile.mkdtemp(prefix="wf-model-surface-")
os.environ["WORKFRAME_AGENTS_DIR"] = tmpdir
os.environ["WORKFRAME_PROJECT"] = "ModelSurfaceTest"
os.environ["NATIVE_PROFILE"] = "surface-test-agent"

spec = importlib.util.spec_from_file_location("wf_server_model_surface", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
sys.modules["wf_server_model_surface"] = server
spec.loader.exec_module(server)
sys.modules["server"] = server  # ponytail: extracted modules resolve _srv() to this instance

PROF = "surface-test-agent"
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

# E: reconcile picks model billing over stale openrouter proxy yaml
(prof_dir / "config.yaml").write_text(
    "model:\n  default: openai-codex/gpt-5.4-mini\n  provider: custom\n"
    "  base_url: http://workframe-api:8080/internal/llm/openrouter/v1\n",
    encoding="utf-8",
)
_orig_picker = server._user_llm_providers_for_picker
_orig_can = server._user_can_use_llm
_orig_sync = server._sync_oauth_llm_to_profile
server._user_llm_providers_for_picker = lambda uid: {"codex"} if uid == "user-1" else set()
server._user_can_use_llm = lambda uid, ws, prov: uid == "user-1" and prov == "codex"
server._sync_oauth_llm_to_profile = lambda *a, **k: None
try:
    assert server._reconcile_profile_llm_for_user(PROF, "user-1", "") is True
    block = server._read_model_block(PROF)
    assert block.get("provider") == "openai-codex"
    assert block.get("default") == "gpt-5.4-mini"
    assert not block.get("base_url")
finally:
    server._user_llm_providers_for_picker = _orig_picker
    server._user_can_use_llm = _orig_can
    server._sync_oauth_llm_to_profile = _orig_sync

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
        PROF, "gpt-5.4-mini", user_id="test-user2", workspace_id="", billing_provider="codex",
    )
finally:
    server._restart_runtime_profile_gateway = _orig_restart
assert applied.get("ok"), applied
runtime_block = server._parse_model_block_from_disk(runtime_prof)
assert runtime_block.get("default") == "gpt-5.4-mini", runtime_block

print("model surface consistency self-check ok")
