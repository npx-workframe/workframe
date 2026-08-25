"""POST /api/install/register-admin must persist email only — no session or owner claim."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

td = Path(tempfile.mkdtemp())
os.environ["WORKFRAME_API_DATA_DIR"] = str(td)
os.environ["HERMES_DATA"] = str(td / "hermes")

import install_api  # noqa: E402
import server  # noqa: E402
import stack_config  # noqa: E402

stack_config.DATA_DIR = td
stack_config.CONFIG_PATH = td / "stack_config.json"


class _CaptureHandler(server.Handler):
    captured: tuple[int, dict, list[tuple[str, str]]] | None = None

    def _json(self, status: int, payload: dict, **kwargs) -> None:  # type: ignore[override]
        headers = kwargs.get("extra_headers") or []
        type(self).captured = (status, payload, list(headers))


def test_register_admin_persists_email_without_session() -> None:
    handler = _CaptureHandler.__new__(_CaptureHandler)
    with patch.object(server, "_install_window_open", return_value=True), patch.object(
        server._zk,
        "create_session_for_email",
    ) as create_session, patch.object(handler, "_first_owner_bootstrap") as bootstrap:
        handler._route_post_install_register_admin(
            {"email": "Owner@Example.com", "display_name": "Owner"},
        )
    create_session.assert_not_called()
    bootstrap.assert_not_called()
    assert _CaptureHandler.captured is not None
    status, body, headers = _CaptureHandler.captured
    assert status == 200
    assert body.get("ok") is True
    assert body.get("admin_email") == "owner@example.com"
    assert "session_id" not in body
    assert not any(h[0].lower() == "set-cookie" for h in headers)
    raw = stack_config.read_stack_raw()
    assert raw["smtp"]["admin_email"] == "owner@example.com"
    assert raw.get("wizard_step") == "theme"
    assert not install_api.install_owner_claimed(str(td / "workframe.db"))


def test_register_admin_rejects_when_install_closed() -> None:
    handler = _CaptureHandler.__new__(_CaptureHandler)
    with patch.object(server, "_install_window_open", return_value=False):
        handler._route_post_install_register_admin({"email": "owner@example.com"})
    assert _CaptureHandler.captured is not None
    assert _CaptureHandler.captured[0] == 403


if __name__ == "__main__":
    test_register_admin_persists_email_without_session()
    test_register_admin_rejects_when_install_closed()
    print("test_install_register_admin: ok")
