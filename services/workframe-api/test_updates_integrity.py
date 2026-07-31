"""ponytail self-check: install drift detection for stack updates.

Run: python services/workframe-api/test_updates_integrity.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import updates  # noqa: E402


def _write_stamp(root: Path, rel: str, version: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"package_version": version}), encoding="utf-8")


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "workframe-manifest.json").write_text(
        json.dumps({"package_version": "0.1.33"}),
        encoding="utf-8",
    )
    data_dir = root / "workframe-api" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "package-version").write_text("0.1.33\n", encoding="utf-8")
    _write_stamp(root, "workframe-api/workframe-api-build.json", "0.1.29")
    _write_stamp(root, "workframe-ui/public/workframe-build.json", "0.1.33")

    os.environ["WORKFRAME_API_DATA_DIR"] = str(data_dir)
    os.environ["WORKFRAME_PROJECT_ROOT"] = str(root)
    os.environ["WORKFRAME_API_VERSION"] = "0.1.29"
    try:
        installed = updates._read_installed_workframe_version(root)
        integrity = updates._workframe_install_integrity(installed, root)
        assert integrity["package_pin"] == "0.1.33", integrity
        assert integrity["api_env"] == "0.1.29", integrity
        assert integrity["api_build"] == "0.1.29", integrity
        assert integrity["ui_build"] == "0.1.33", integrity
        assert not integrity["ok"], integrity
        assert any("compose env" in reason for reason in integrity["drift_reasons"]), integrity

        aligned = updates._workframe_install_integrity(
            {"package": "0.1.33", "api": "0.1.33"},
            root,
        )
        _write_stamp(root, "workframe-api/workframe-api-build.json", "0.1.33")
        aligned = updates._workframe_install_integrity(
            {"package": "0.1.33", "api": "0.1.33"},
            root,
        )
        assert aligned["ok"], aligned
    finally:
        os.environ.pop("WORKFRAME_API_DATA_DIR", None)
        os.environ.pop("WORKFRAME_PROJECT_ROOT", None)
        os.environ.pop("WORKFRAME_API_VERSION", None)

print("updates integrity self-check ok")
