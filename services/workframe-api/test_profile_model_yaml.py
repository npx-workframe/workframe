#!/usr/bin/env python3
"""Coalesce corrupt duplicate model blocks + profile_config_yaml writer (WF-033)."""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("WORKFRAME_AGENTS_DIR", tempfile.mkdtemp(prefix="wf-yaml-test-"))
os.environ.setdefault("WORKFRAME_PROJECT", "YamlTest")
os.environ.setdefault("NATIVE_PROFILE", "yaml-test-agent")

spec = importlib.util.spec_from_file_location("wf_server_yaml_test", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
sys.modules["wf_server_yaml_test"] = server
spec.loader.exec_module(server)

import profile_config_yaml  # noqa: E402

BROKEN = """model:
  default: gpt-5.4-medium
  provider: openai-codex
model:
  default: gpt-5.4-medium
  - provider: openai-codex
fallback_providers:
  - provider: openai-codex
    model: gpt-5.4-mini
toolsets:
"""

prof = "yaml-test-agent"
prof_dir = server._profile_dir(prof)
prof_dir.mkdir(parents=True, exist_ok=True)
cfg_path = prof_dir / "config.yaml"
cfg_path.write_text(BROKEN, encoding="utf-8")

server._normalize_profile_config_yaml(prof)
fixed = cfg_path.read_text(encoding="utf-8")
assert fixed.count("\nmodel:\n") + fixed.count("model:\n") <= 2, fixed
assert "  - provider:" not in fixed.split("fallback_providers:")[0], fixed
parsed = yaml.safe_load(fixed)
assert isinstance(parsed.get("model"), dict), parsed
assert parsed["model"]["default"] == "gpt-5.4-medium"
assert parsed["model"]["provider"] == "openai-codex"
assert len(parsed.get("fallback_providers") or []) == 1
assert "toolsets" in parsed

# Round-trip via update_model_surface preserves non-model keys
round_prof = "yaml-round-trip"
round_dir = server._profile_dir(round_prof)
round_dir.mkdir(parents=True, exist_ok=True)
round_path = round_dir / "config.yaml"
round_path.write_text(
    "# picker note\nmodel:\n  default: old-model\n  provider: openrouter\ncron: []\n",
    encoding="utf-8",
)
profile_config_yaml.update_model_surface(
    round_path, default="new-model", provider="custom", base_url="http://proxy/v1",
)
rt = yaml.safe_load(round_path.read_text(encoding="utf-8"))
assert rt["model"]["default"] == "new-model"
assert rt["model"]["provider"] == "custom"
assert rt["model"]["base_url"] == "http://proxy/v1"
assert rt.get("cron") == []
assert "# picker note" not in round_path.read_text(encoding="utf-8")  # comments not preserved

# Missing file: writer creates parent dirs + config
missing_prof = "yaml-missing"
missing_dir = server._profile_dir(missing_prof)
missing_path = missing_dir / "config.yaml"
if missing_path.is_file():
    missing_path.unlink()
profile_config_yaml.update_model_surface(
    missing_path, default="gpt-5.4-mini", provider="openai-codex",
)
assert missing_path.is_file()
loaded = yaml.safe_load(missing_path.read_text(encoding="utf-8"))
assert loaded["model"]["default"] == "gpt-5.4-mini"

# Coalesce flag drops duplicate blocks
dup_path = round_dir / "dup.yaml"
dup_path.write_text(BROKEN, encoding="utf-8")
profile_config_yaml.update_model_surface(
    dup_path,
    default="gpt-5.4-medium",
    provider="openai-codex",
    fallback_chain=[{"provider": "openai-codex", "model": "gpt-5.4-mini"}],
    coalesce=True,
)
dup_text = dup_path.read_text(encoding="utf-8")
assert dup_text.count("\nmodel:\n") + dup_text.count("model:\n") <= 2, dup_text
dup_parsed = yaml.safe_load(dup_text)
assert dup_parsed["model"]["default"] == "gpt-5.4-medium"

print("profile model yaml coalesce self-check ok")
