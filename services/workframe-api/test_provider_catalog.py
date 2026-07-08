"""WF-032 provider_catalog self-check."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import provider_catalog  # noqa: E402


def test_catalog_lookup() -> None:
    gh = provider_catalog.catalog_provider("github")
    assert gh is not None
    assert gh.get("connect_mode") == "oauth"
    assert provider_catalog.catalog_provider_for_llm("openai-codex") is not None


def test_user_only() -> None:
    assert provider_catalog.provider_user_only("github")
    assert not provider_catalog.provider_user_only("openrouter")


if __name__ == "__main__":
    test_catalog_lookup()
    test_user_only()
    print("test_provider_catalog: ok")
