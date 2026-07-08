"""ponytail self-check: /api/meta exposes package + UI build stamp (WF-012).

Run: python services/workframe-api/test_api_meta_build_stamp.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import api_meta  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    ui_public = Path(tmp) / "workframe-ui" / "public"
    ui_public.mkdir(parents=True)
    stamp = {
        "package_version": "9.9.9",
        "bundled_at": "2026-07-08T12:00:00.000Z",
        "git_ref": "abc1234",
    }
    (ui_public / "workframe-build.json").write_text(json.dumps(stamp), encoding="utf-8")
    os.environ["WORKFRAME_PROJECT_ROOT"] = tmp
    os.environ["WORKFRAME_API_VERSION"] = "9.9.9"
    try:
        ui = api_meta._ui_build_stamp()
        assert ui["package_version"] == "9.9.9", ui
        assert ui["git_ref"] == "abc1234", ui
    finally:
        os.environ.pop("WORKFRAME_PROJECT_ROOT", None)
        os.environ.pop("WORKFRAME_API_VERSION", None)

print("api meta build stamp self-check ok")
