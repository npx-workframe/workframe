"""Workspace-backed LLM readiness self-check."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import provider_bootstrap  # noqa: E402


def test_workspace_vault_binding_counts_as_llm_provider(monkeypatch) -> None:
    server = SimpleNamespace(
        PROVIDER_CONNECT_CATALOG=(
            {"id": "openrouter", "category": "llm"},
            {"id": "github", "category": "dev"},
        ),
        _resolve_credential=lambda _user, _workspace, provider: (
            {"provider": provider, "credential_ref": "vault:shared"}
            if provider == "openrouter"
            else None
        ),
        _credential_secret=lambda binding, _user: "shared-test-value" if binding else "",
    )
    monkeypatch.setattr(provider_bootstrap, "_srv", lambda: server)

    assert provider_bootstrap._workspace_has_llm_provider("workspace-1") is True


if __name__ == "__main__":
    server = SimpleNamespace(
        PROVIDER_CONNECT_CATALOG=({"id": "openrouter", "category": "llm"},),
        _resolve_credential=lambda *_args: {"credential_ref": "vault:shared"},
        _credential_secret=lambda *_args: "shared-test-value",
    )
    with patch.object(provider_bootstrap, "_srv", return_value=server):
        assert provider_bootstrap._workspace_has_llm_provider("workspace-1") is True
    print("test_provider_bootstrap: ok")
