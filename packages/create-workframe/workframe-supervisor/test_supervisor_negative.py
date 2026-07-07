"""WF-011 supervisor negative tests — docker boundary, profile/path misuse, auth.

Run: python services/workframe-supervisor/test_supervisor_negative.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import server as supervisor
from profile_secret_policy import exec_blocked_for_profile, is_secret_read_attempt


def test_secret_read_blocked() -> None:
    cmd = ["sh", "-lc", "cat /opt/data/profiles/u-alice-dev/.env"]
    assert is_secret_read_attempt(cmd)
    assert exec_blocked_for_profile(cmd, "u-alice-dev")


def test_foreign_profile_secrets_blocked() -> None:
    cmd = ["cat", "/opt/data/profiles/u-bob-dev/.env"]
    assert exec_blocked_for_profile(cmd, "u-alice-dev")


def test_invalid_profile_slug_rejected() -> None:
    for bad in ("", "../etc", "UPPER", "a" * 70):
        try:
            supervisor.safe_profile_slug(bad)
            raise AssertionError(f"expected ValueError for {bad!r}")
        except ValueError:
            pass


def test_supervisor_auth_required() -> None:
    supervisor.SUPERVISOR_TOKEN = "neg-test-token"

    class _Handler:
        headers: dict[str, str] = {}

    assert not supervisor._auth_ok(_Handler())  # type: ignore[arg-type]
    _Handler.headers = {"Authorization": "Bearer neg-test-token"}
    assert supervisor._auth_ok(_Handler())  # type: ignore[arg-type]


def test_raw_container_exec_disabled_by_default() -> None:
    os.environ.pop("WORKFRAME_SUPERVISOR_ALLOW_RAW_EXEC", None)
    assert os.environ.get("WORKFRAME_SUPERVISOR_ALLOW_RAW_EXEC", "0") != "1"


def test_api_compose_public_has_no_docker_sock() -> None:
  repo = Path(__file__).resolve().parents[2]
  public = (repo / "infra" / "compose" / "workframe" / "docker-compose.public.yml").read_text(
      encoding="utf-8"
  )
  api_block = public.split("workframe-api:")[1].split("workframe-supervisor:")[0]
  assert "/var/run/docker.sock" not in api_block
  assert "WORKFRAME_SUPERVISOR_ALLOW_RAW_EXEC=0" in public


def main() -> None:
    test_secret_read_blocked()
    test_foreign_profile_secrets_blocked()
    test_invalid_profile_slug_rejected()
    test_supervisor_auth_required()
    test_raw_container_exec_disabled_by_default()
    test_api_compose_public_has_no_docker_sock()
    print("supervisor negative tests ok")


if __name__ == "__main__":
    main()
