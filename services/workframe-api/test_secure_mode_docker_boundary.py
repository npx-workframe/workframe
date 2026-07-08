"""WF-NS-P1 secure-mode docker socket boundary self-check."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402


def test_docker_request_blocked_in_secure_mode() -> None:
    prev = server.SECURE_MODE
    try:
        server.SECURE_MODE = True
        try:
            server._docker_request("GET", "/containers/json")
            raise AssertionError("expected RuntimeError in SECURE_MODE")
        except RuntimeError as exc:
            assert "SECURE_MODE" in str(exc)
    finally:
        server.SECURE_MODE = prev


def test_public_compose_api_has_no_docker_sock() -> None:
    """Compose config assertion — complements WF-011 supervisor negatives."""
    repo = Path(__file__).resolve().parents[2]
    public = (repo / "infra" / "compose" / "workframe" / "docker-compose.public.yml").read_text(
        encoding="utf-8"
    )
    api_block = public.split("workframe-api:")[1].split("workframe-supervisor:")[0]
    assert "/var/run/docker.sock" not in api_block


if __name__ == "__main__":
    test_docker_request_blocked_in_secure_mode()
    test_public_compose_api_has_no_docker_sock()
    print("test_secure_mode_docker_boundary: ok")
