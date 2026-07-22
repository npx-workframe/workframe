"""Shared agent identity vs per-user runtime proxy regression checks."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

os.environ.setdefault("WORKFRAME_API_DATA_DIR", str(API_DIR / ".tmp-test-data"))
os.environ.setdefault("HERMES_DATA", str(API_DIR / ".tmp-test-hermes"))
os.environ.setdefault("DEV_LOCAL_UNSAFE", "true")

import crew_registry  # noqa: E402
import hermes_profiles  # noqa: E402
import runtime_cohort  # noqa: E402
import server  # noqa: E402


def test_runtime_display_name_comes_from_shared_agent() -> None:
    with (
        patch.object(server, "_agent_db_display_name", return_value="Shared Architect"),
        patch.object(server, "_agent_registry_row", return_value={"display_name": "Template Architect"}),
    ):
        assert (
            runtime_cohort._runtime_display_label("bob-user", "architect", "workspace-1")
            == "Shared Architect"
        )


def test_native_display_name_comes_from_shared_agent() -> None:
    with (
        patch.object(server, "NATIVE_PROFILE", "workframe-agent"),
        patch.object(hermes_profiles, "_agent_db_display_name", return_value="Shared Concierge"),
    ):
        assert hermes_profiles._native_display_name() == "Shared Concierge"


def test_runtime_identity_fields_ignore_runtime_registry_metadata() -> None:
    def registry_row(slug: str) -> dict[str, str]:
        if slug.startswith("u-"):
            return {"display_name": "Bob's Clone", "tagline": "Runtime drift"}
        return {"display_name": "Shared Agent", "tagline": "Workspace identity", "role": "Architect"}

    with (
        patch.object(crew_registry, "_agent_registry_row", side_effect=registry_row),
        patch.object(crew_registry, "_workspace_agent_identities", return_value={}),
        patch.object(server, "_profile_display_name", return_value="Fallback"),
        patch.object(server, "_profile_role", return_value="Fallback role"),
        patch.object(server, "_resolve_avatar_fields", side_effect=lambda row: row),
    ):
        identity = crew_registry._agent_identity_fields(
            "u-bob-user-architect",
            "workspace-1",
            "bob-user",
        )
    assert identity["display_name"] == "Shared Agent"
    assert identity["tagline"] == "Workspace identity"
    assert identity["role"] == "Architect"


def test_runtime_identity_sync_preserves_credentials() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        template_dir = root / "architect"
        runtime_dir = root / "u-bob-architect"
        template_dir.mkdir()
        runtime_dir.mkdir()
        (template_dir / "SOUL.md").write_text("shared soul\n", encoding="utf-8")
        (template_dir / "AGENTS.md").write_text("shared agents\n", encoding="utf-8")
        (runtime_dir / "SOUL.md").write_text("stale runtime soul\n", encoding="utf-8")
        (runtime_dir / "AGENTS.md").write_text("stale runtime agents\n", encoding="utf-8")
        (runtime_dir / ".env").write_text("OPENROUTER_API_KEY=user-secret\n", encoding="utf-8")

        with (
            patch.object(server, "_profile_dir", side_effect=lambda slug: root / slug),
            patch.object(runtime_cohort, "_ensure_profile_terminal_cwd", return_value=None),
        ):
            runtime_cohort._backfill_runtime_identity("u-bob-architect", "architect")

        assert (runtime_dir / "SOUL.md").read_text(encoding="utf-8") == "shared soul\n"
        assert (runtime_dir / "AGENTS.md").read_text(encoding="utf-8") == "shared agents\n"
        assert (runtime_dir / ".env").read_text(encoding="utf-8") == "OPENROUTER_API_KEY=user-secret\n"


if __name__ == "__main__":
    test_runtime_display_name_comes_from_shared_agent()
    test_native_display_name_comes_from_shared_agent()
    test_runtime_identity_fields_ignore_runtime_registry_metadata()
    test_runtime_identity_sync_preserves_credentials()
    print("test_agent_identity_authority: ok")
