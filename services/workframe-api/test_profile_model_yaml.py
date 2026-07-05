#!/usr/bin/env python3
"""Coalesce corrupt duplicate model blocks (install wizard regression)."""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("WORKFRAME_AGENTS_DIR", tempfile.mkdtemp(prefix="wf-yaml-test-"))
os.environ.setdefault("WORKFRAME_PROJECT", "YamlTest")
os.environ.setdefault("NATIVE_PROFILE", "yaml-test-agent")

spec = importlib.util.spec_from_file_location("wf_server_yaml_test", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
sys.modules["wf_server_yaml_test"] = server
spec.loader.exec_module(server)

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
(prof_dir / "config.yaml").write_text(BROKEN, encoding="utf-8")

server._normalize_profile_config_yaml(prof)
fixed = (prof_dir / "config.yaml").read_text(encoding="utf-8")
assert fixed.count("\nmodel:\n") + fixed.count("model:\n") <= 2, fixed
assert "  - provider:" not in fixed.split("fallback_providers:")[0], fixed

import yaml

yaml.safe_load(fixed)
print("profile model yaml coalesce self-check ok")
