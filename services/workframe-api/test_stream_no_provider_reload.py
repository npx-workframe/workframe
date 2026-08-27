"""Skip-without-key must not bounce the runtime gateway before concierge."""

from __future__ import annotations

import json
import os
import sys
from io import BytesIO
from pathlib import Path

API_DIR = Path(__file__).resolve().parent
os.environ.setdefault("WORKFRAME_API_DATA_DIR", str(API_DIR / ".tmp-test-data-stream"))
os.environ.setdefault("HERMES_DATA", str(API_DIR / ".tmp-test-hermes-stream"))
os.environ.setdefault("DEV_LOCAL_UNSAFE", "true")
os.environ.setdefault("WORKFRAME_DEPLOYMENT_MODE", "trusted_team")
(API_DIR / ".tmp-test-data-stream").mkdir(exist_ok=True)
(API_DIR / ".tmp-test-hermes-stream").mkdir(exist_ok=True)

sys.path.insert(0, str(API_DIR))

import chat_stream as cs  # noqa: E402


class _FakeSrv:
    reloads = 0
    bootstraps = 0

    def _resolve_bind_profile_arg(self, profile, user_id, room_id, workspace_id):
        return "u-owner-agent", "mybusiness-agent"

    def _read_model_block(self, profile):
        return {"default": "anthropic/claude-opus-4.6", "provider": "custom"}

    def _llm_billing_provider(self, profile, user_id="", workspace_id="", block=None):
        return "openrouter"

    def _user_can_use_llm(self, user_id, workspace_id, provider):
        return False

    def _profile_api_port(self, profile):
        return 18621

    def _bootstrap_profile_providers(self, profile, user_id="", workspace_id=""):
        type(self).bootstraps += 1
        return True

    def _reload_runtime_profile_gateway(self, profile, wait_healthy=True):
        type(self).reloads += 1


class _FakeHandler:
    def __init__(self) -> None:
        self.wfile = BytesIO()
        self.headers_sent = []

    def send_response(self, code):
        self.headers_sent.append(("response", code))

    def send_header(self, k, v):
        self.headers_sent.append((k, v))

    def end_headers(self):
        self.headers_sent.append(("end", True))


def test_no_provider_skips_gateway_reload() -> None:
    _FakeSrv.reloads = 0
    _FakeSrv.bootstraps = 0
    orig = cs._srv
    cs._srv = lambda: _FakeSrv()  # type: ignore[assignment]
    try:
        handler = _FakeHandler()
        cs.stream_profile_chat(
            handler,  # type: ignore[arg-type]
            "mybusiness-agent",
            {
                "user_id": "user-1",
                "workspace_id": "ws-1",
                "room_id": "room-1",
                "session_id": "sess-1",
                "text": "dm ping 2",
            },
        )
    finally:
        cs._srv = orig
    body = handler.wfile.getvalue().decode("utf-8")
    assert _FakeSrv.bootstraps == 0
    assert _FakeSrv.reloads == 0
    assert "event: concierge" in body
    assert "event: done" in body
    assert "Contacting model" in body


if __name__ == "__main__":
    test_no_provider_skips_gateway_reload()
    print("PASS")
