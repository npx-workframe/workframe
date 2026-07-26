"""Shared agent identity vs per-user runtime proxy regression checks."""

from __future__ import annotations

import json
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
import hermes_admin  # noqa: E402
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


def _native_profile_fixture() -> tuple[Path, Path, Path, str]:
    root = Path(tempfile.mkdtemp())
    native = "workframe-agent"
    prof_dir = root / native
    prof_dir.mkdir(parents=True)
    soul_path = prof_dir / "SOUL.md"
    soul_path.write_text(
        "# Workframe concierge\n\nYou are the Workframe botfather orchestrator.\n",
        encoding="utf-8",
    )
    agents_json = root / "workframe" / "agents.json"
    agents_json.parent.mkdir(parents=True, exist_ok=True)
    agents_json.write_text(
        json.dumps({"version": 1, "agents": {native: {"profile": native}}}),
        encoding="utf-8",
    )
    return root, soul_path, agents_json, native


def test_native_admin_soul_does_not_modify_soul_md() -> None:
    root, soul_path, agents_json, native = _native_profile_fixture()
    original = soul_path.read_text(encoding="utf-8")
    try:
        with (
            patch.object(server, "NATIVE_PROFILE", native),
            patch.object(server, "HERMES_DATA", root),
            patch.object(server, "AGENTS_JSON", agents_json),
            patch.object(server, "_profile_dir", side_effect=lambda slug: root / slug),
            patch.object(server, "resolve_validated_profile", side_effect=lambda p: p),
            patch.object(server, "_is_native_profile", side_effect=lambda p: p == native),
            patch.object(server, "_primary_profile", return_value=native),
        ):
            result = hermes_admin.profile_soul_set(native, "Owner manager tone.", layer="admin")
            assert result.get("ok")
            assert result.get("target") == "admin_soul"
            assert soul_path.read_text(encoding="utf-8") == original
    finally:
        import shutil

        shutil.rmtree(root, ignore_errors=True)


def test_composed_soul_includes_admin_and_workspace_spice() -> None:
    root, soul_path, agents_json, native = _native_profile_fixture()
    try:
        with (
            patch.object(server, "NATIVE_PROFILE", native),
            patch.object(server, "HERMES_DATA", root),
            patch.object(server, "AGENTS_JSON", agents_json),
            patch.object(server, "_profile_dir", side_effect=lambda slug: root / slug),
            patch.object(server, "resolve_validated_profile", side_effect=lambda p: p),
            patch.object(server, "_is_native_profile", side_effect=lambda p: p == native),
            patch.object(server, "_primary_profile", return_value=native),
            patch.object(
                server,
                "_workspace_agent_spice",
                return_value="Prefer concise bullet replies.",
            ),
        ):
            hermes_admin.profile_soul_set(native, "Lead with empathy.", layer="admin")
            composed = hermes_profiles._profile_soul_text(native, "workspace-1")
            assert "## Manager identity" in composed
            assert "Lead with empathy." in composed
            assert "## Workspace preferences" in composed
            assert "Prefer concise bullet replies." in composed
            layers = hermes_admin.profile_soul_get(native, "workspace-1")
            assert layers["admin"] == "Lead with empathy."
            assert layers["workspace_spice"] == "Prefer concise bullet replies."
            assert "Lead with empathy." in layers["composed"]
    finally:
        import shutil

        shutil.rmtree(root, ignore_errors=True)


def test_runtime_inherits_native_admin_soul() -> None:
    root, _, agents_json, native = _native_profile_fixture()
    runtime = "u-alice-workframe-agent"
    (root / runtime).mkdir()
    (root / runtime / "SOUL.md").write_text("runtime stub\n", encoding="utf-8")
    try:
        with (
            patch.object(server, "NATIVE_PROFILE", native),
            patch.object(server, "HERMES_DATA", root),
            patch.object(server, "AGENTS_JSON", agents_json),
            patch.object(server, "_profile_dir", side_effect=lambda slug: root / slug),
            patch.object(server, "resolve_validated_profile", side_effect=lambda p: p),
            patch.object(server, "_is_native_profile", side_effect=lambda p: p == native),
            patch.object(server, "_primary_profile", return_value=native),
            patch.object(server, "_is_runtime_profile_slug", side_effect=lambda p: p.startswith("u-")),
        ):
            hermes_admin.profile_soul_set(native, "Shared native admin overlay.", layer="admin")
            composed = hermes_profiles._profile_soul_text(runtime)
            assert "## Manager identity" in composed
            assert "Shared native admin overlay." in composed
    finally:
        import shutil

        shutil.rmtree(root, ignore_errors=True)


def test_child_user_soul_overlay_still_works() -> None:
    root = Path(tempfile.mkdtemp())
    child = "research-analyst"
    prof_dir = root / child
    prof_dir.mkdir(parents=True)
    (prof_dir / "SOUL.md").write_text(
        "# Research Analyst\n\nMission: dig into sources.\n",
        encoding="utf-8",
    )
    agents_json = root / "workframe" / "agents.json"
    agents_json.parent.mkdir(parents=True, exist_ok=True)
    agents_json.write_text(json.dumps({"version": 1, "agents": {}}), encoding="utf-8")
    try:
        with (
            patch.object(server, "NATIVE_PROFILE", "workframe-agent"),
            patch.object(server, "HERMES_DATA", root),
            patch.object(server, "AGENTS_JSON", agents_json),
            patch.object(server, "_profile_dir", side_effect=lambda slug: root / slug),
            patch.object(server, "resolve_validated_profile", side_effect=lambda p: p),
            patch.object(server, "_is_native_profile", side_effect=lambda p: p == "workframe-agent"),
            patch.object(server, "_is_runtime_profile_slug", return_value=False),
            patch.object(server, "_primary_profile", return_value="workframe-agent"),
        ):
            result = hermes_admin.profile_soul_set(child, "Always cite sources.", layer="user")
            assert result.get("ok")
            assert result.get("target") == "user_soul"
            composed = hermes_profiles._profile_soul_text(child)
            assert "## User preferences" in composed
            assert "Always cite sources." in composed
            assert "## Manager identity" not in composed
    finally:
        import shutil

        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    test_runtime_display_name_comes_from_shared_agent()
    test_native_display_name_comes_from_shared_agent()
    test_runtime_identity_fields_ignore_runtime_registry_metadata()
    test_runtime_identity_sync_preserves_credentials()
    test_native_admin_soul_does_not_modify_soul_md()
    test_composed_soul_includes_admin_and_workspace_spice()
    test_runtime_inherits_native_admin_soul()
    test_child_user_soul_overlay_still_works()
    print("test_agent_identity_authority: ok")
