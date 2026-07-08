"""WF-032 hermes_admin self-check."""

from __future__ import annotations

import os
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

os.environ.setdefault("WORKFRAME_API_DATA_DIR", str(API_DIR / ".tmp-test-data"))
os.environ.setdefault("HERMES_DATA", str(API_DIR / ".tmp-test-hermes"))
os.environ.setdefault("DEV_LOCAL_UNSAFE", "true")

import hermes_admin  # noqa: E402


def test_resolve_command_known() -> None:
    entry = hermes_admin._resolve_command("/help")
    assert entry is not None
    assert entry["name"] == "/help"
    assert entry["dispatch"] == "client:openHelp"


def test_resolve_command_alias() -> None:
    entry = hermes_admin._resolve_command("reset")
    assert entry is not None
    assert entry["name"] == "/new"


def test_resolve_command_unknown() -> None:
    assert hermes_admin._resolve_command("/not-a-real-command") is None


def test_commands_catalog_shape() -> None:
    catalog = hermes_admin.hermes_commands_catalog()
    assert catalog["ok"] is True
    assert isinstance(catalog["categories"], list)
    assert isinstance(catalog["entries"], list)
    assert all(entry.get("wired") is True for entry in catalog["entries"])
    assert not any(entry.get("wip") for entry in catalog["entries"])


def test_commands_exec_client_dispatch() -> None:
    result = hermes_admin.hermes_commands_exec("/help")
    assert result["ok"] is True
    assert result["dispatched"] == "client"
    assert result["handler"] == "openHelp"


def test_commands_exec_not_slash() -> None:
    result = hermes_admin.hermes_commands_exec("hello")
    assert result["ok"] is False
    assert result["error"] == "not a slash command"


def test_gquota_stub() -> None:
    result = hermes_admin.hermes_gquota()
    assert result["ok"] is False or "configured" in result


if __name__ == "__main__":
    test_resolve_command_known()
    test_resolve_command_alias()
    test_resolve_command_unknown()
    test_commands_catalog_shape()
    test_commands_exec_client_dispatch()
    test_commands_exec_not_slash()
    test_gquota_stub()
    print("test_hermes_admin: ok")
