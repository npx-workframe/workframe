"""api_errors public payload self-check."""
from __future__ import annotations

import urllib.error

import api_errors


def main() -> None:
    raw = (
        "runtime profile create failed: Traceback (most recent call last):\n"
        '  File "/opt/hermes/hermes_cli/profiles.py", line 1\n'
        "PermissionError: [Errno 13] Permission denied: '/opt/data/profiles/u-test-agent'"
    )
    payload = api_errors.public_api_error_payload(ValueError(raw))
    assert payload["error"] == "runtime_profile_permission_denied"
    assert "Traceback" not in payload["message"]
    assert payload["message"]
    assert payload["hint"]

    assert api_errors.http_status_for_code("no_session") == 401
    assert api_errors.http_status_for_code("room_not_found") == 404

    refused = api_errors.public_api_error_payload(
        urllib.error.URLError("[Errno 111] Connection refused"),
    )
    assert refused["error"] == "runtime_profile_api_config_failed"

    print("test_api_errors: ok")


if __name__ == "__main__":
    main()
