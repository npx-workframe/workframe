"""Local bootstrap must require a real owner email — no synthetic placeholders."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

os.environ.setdefault("WORKFRAME_API_DATA_DIR", str(API_DIR / ".tmp-test-data"))
os.environ.setdefault("HERMES_DATA", str(API_DIR / ".tmp-test-hermes"))
os.environ.setdefault("DEV_LOCAL_UNSAFE", "true")
os.environ["DEPLOYMENT_MODE"] = "single_user_local"

import server  # noqa: E402


class _CaptureHandler(server.Handler):
    captured: tuple[int, dict] | None = None

    def _json(self, status: int, payload: dict, **kwargs) -> None:  # type: ignore[override]
        type(self).captured = (status, payload)


def test_local_bootstrap_rejects_missing_email() -> None:
    handler = _CaptureHandler.__new__(_CaptureHandler)
    with patch.object(server, "DEPLOYMENT_MODE", "single_user_local"), patch.object(
        server, "_install_window_open", return_value=True,
    ):
        handler._route_post_auth_local_bootstrap({})
    assert _CaptureHandler.captured is not None
    status, body = _CaptureHandler.captured
    assert status == 400
    assert body.get("error") == "email_required"


def test_local_bootstrap_uses_submitted_email() -> None:
    handler = _CaptureHandler.__new__(_CaptureHandler)
    with patch.object(server, "DEPLOYMENT_MODE", "single_user_local"), patch.object(
        server, "_install_window_open", return_value=True,
    ), patch.object(
        server._zk,
        "create_session_for_email",
        return_value={"user_id": "u-test", "session_id": "s-test", "refresh_token": "r-test"},
    ) as create_session, patch.object(handler, "_ensure_user"), patch.object(
        handler, "_first_owner_bootstrap",
    ), patch.object(server, "_session_profile_payload", return_value={"ok": True}), patch.object(
        server, "_session_cookie_secure", return_value=False,
    ), patch.object(
        server._zk, "session_cookie_value", return_value="cookie=test",
    ):
        handler._route_post_auth_local_bootstrap(
            {"email": "Alan@Click.Blue", "display_name": "Alan"},
        )
    create_session.assert_called_once_with("alan@click.blue")
    assert _CaptureHandler.captured is not None
    assert _CaptureHandler.captured[0] == 200


if __name__ == "__main__":
    test_local_bootstrap_rejects_missing_email()
    test_local_bootstrap_uses_submitted_email()
    print("ok")
