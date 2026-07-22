from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import route_registry  # noqa: E402
import server  # noqa: E402
import workspace_files  # noqa: E402


def _workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setattr(server, "WORKSPACE", root)
    return root


def test_files_archive_preserves_relative_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = _workspace(monkeypatch, tmp_path)
    (root / "docs").mkdir()
    (root / "docs" / "notes.txt").write_text("hello", encoding="utf-8")
    (root / "image.bin").write_bytes(b"\x00\x01")

    payload = workspace_files.files_archive(["docs/notes.txt", "image.bin", "docs/notes.txt"])
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert archive.namelist() == ["docs/notes.txt", "image.bin"]
        assert archive.read("docs/notes.txt") == b"hello"
        assert archive.read("image.bin") == b"\x00\x01"


def test_files_archive_expands_folders_and_deduplicates_descendants(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _workspace(monkeypatch, tmp_path)
    (root / "assets" / "nested").mkdir(parents=True)
    (root / "assets" / "one.txt").write_text("one", encoding="utf-8")
    (root / "assets" / "nested" / "two.txt").write_text("two", encoding="utf-8")
    (root / "assets" / "nested" / ".env").write_text("SECRET=value", encoding="utf-8")

    payload = workspace_files.files_archive(["assets", "assets/nested/two.txt"])

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert archive.namelist() == ["assets/nested/two.txt", "assets/one.txt"]
        assert archive.read("assets/nested/two.txt") == b"two"
        assert ".env" not in "\n".join(archive.namelist())


def test_files_archive_folder_respects_resolved_file_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _workspace(monkeypatch, tmp_path)
    (root / "assets").mkdir()
    (root / "assets" / "one.txt").write_text("one", encoding="utf-8")
    (root / "assets" / "two.txt").write_text("two", encoding="utf-8")
    monkeypatch.setattr(workspace_files, "MAX_FILE_ACTION_COUNT", 1)

    with pytest.raises(ValueError, match="select at most 1 files"):
        workspace_files.files_archive(["assets"])


def test_files_archive_rejects_protected_and_oversized_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _workspace(monkeypatch, tmp_path)
    (root / ".env").write_text("SECRET=value", encoding="utf-8")
    (root / "large.bin").write_bytes(b"12")

    with pytest.raises(PermissionError, match="protected_env_file"):
        workspace_files.files_archive([".env"])

    monkeypatch.setattr(workspace_files, "MAX_ARCHIVE_BYTES", 1)
    with pytest.raises(ValueError, match="100 MB download limit"):
        workspace_files.files_archive(["large.bin"])


def test_files_delete_preflights_complete_batch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = _workspace(monkeypatch, tmp_path)
    keep = root / "keep.txt"
    keep.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="file not found"):
        workspace_files.files_delete(["keep.txt", "missing.txt"])

    assert keep.is_file()


def test_files_delete_removes_selected_files_and_routes_require_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _workspace(monkeypatch, tmp_path)
    first = root / "first.txt"
    second = root / "nested" / "second.txt"
    second.parent.mkdir()
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    result = workspace_files.files_delete(["first.txt", "nested/second.txt"])

    assert result == {
        "ok": True,
        "deleted": ["first.txt", "nested/second.txt"],
        "count": 2,
    }
    assert not first.exists()
    assert not second.exists()
    assert route_registry.resolve_auth_level("POST", "/api/files/archive") == route_registry.AuthLevel.SESSION
    assert route_registry.resolve_auth_level("POST", "/api/files/delete") == route_registry.AuthLevel.SESSION
