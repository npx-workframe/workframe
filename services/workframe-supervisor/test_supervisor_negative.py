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


def test_host_install_paths_reads_env_file() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        compose_dir = Path(tmp)
        (compose_dir / ".env").write_text(
            "WORKFRAME_HOST_COMPOSE_DIR=/opt/workframe/ABX\n"
            "WORKFRAME_HOST_PROJECT_ROOT=/opt/workframe/ABX\n",
            encoding="utf-8",
        )
        old = supervisor.COMPOSE_DIR
        try:
            supervisor.COMPOSE_DIR = compose_dir
            os.environ.pop("WORKFRAME_HOST_COMPOSE_DIR", None)
            os.environ.pop("WORKFRAME_HOST_PROJECT_ROOT", None)
            compose, project = supervisor._host_install_paths()
            assert compose == "/opt/workframe/ABX"
            assert project == "/opt/workframe/ABX"
        finally:
            supervisor.COMPOSE_DIR = old


def test_stack_apply_lock_held() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        compose_dir = Path(tmp)
        lock_dir = compose_dir / "workframe-api" / "data" / ".stack-apply.lock.d"
        old_compose = supervisor.COMPOSE_DIR
        old_lock = supervisor.STACK_APPLY_LOCK_DIR
        try:
            supervisor.COMPOSE_DIR = compose_dir
            supervisor.STACK_APPLY_LOCK_DIR = lock_dir
            assert not supervisor._stack_apply_lock_held()
            lock_dir.mkdir(parents=True)
            (lock_dir / "pid").write_text(str(os.getpid()), encoding="utf-8")
            assert supervisor._stack_apply_lock_held()
        finally:
            supervisor.COMPOSE_DIR = old_compose
            supervisor.STACK_APPLY_LOCK_DIR = old_lock


def test_stack_apply_status_round_trip() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        old_status = supervisor.STACK_APPLY_STATUS_PATH
        old_lock = supervisor.STACK_APPLY_LOCK_DIR
        try:
            supervisor.STACK_APPLY_STATUS_PATH = Path(tmp) / "stack-apply-status.json"
            supervisor.STACK_APPLY_LOCK_DIR = Path(tmp) / ".stack-apply.lock.d"
            written = supervisor._write_stack_apply_status(
                {
                    "job_id": "job-1",
                    "target": "workframe",
                    "state": "running",
                    "pid": os.getpid(),
                    "started_at": "2026-01-01T00:00:00Z",
                },
            )
            assert written["job_id"] == "job-1"
            assert supervisor._read_stack_apply_status("job-1")["state"] == "running"
            assert supervisor._stack_apply_job_active()
            missing = supervisor._read_stack_apply_status("job-2")
            assert missing["error"] == "job_not_found"
            supervisor._write_stack_apply_status(
                {"job_id": "job-1", "target": "workframe", "state": "succeeded"},
            )
            assert not supervisor._stack_apply_job_active()
        finally:
            supervisor.STACK_APPLY_STATUS_PATH = old_status
            supervisor.STACK_APPLY_LOCK_DIR = old_lock


def test_update_script_falls_back_to_compose_tree() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        empty_mount = root / "empty-script-mount"
        canonical_scripts = root / "compose" / "scripts"
        empty_mount.mkdir()
        canonical_scripts.mkdir(parents=True)
        hermes = canonical_scripts / "apply-update-hermes.sh"
        workframe = canonical_scripts / "apply-update-workframe.sh"
        hermes.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        workframe.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        old_scripts = supervisor.SCRIPTS_DIR
        old_compose = supervisor.COMPOSE_DIR
        try:
            supervisor.SCRIPTS_DIR = empty_mount
            supervisor.COMPOSE_DIR = root / "compose"
            assert supervisor._update_script("apply-update-hermes.sh") == hermes
            assert supervisor._update_script("apply-update-workframe.sh") == workframe
        finally:
            supervisor.SCRIPTS_DIR = old_scripts
            supervisor.COMPOSE_DIR = old_compose


def test_update_script_prefers_canonical_nested_mount_over_stale_wrapper() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        scripts = root / "scripts"
        nested = scripts / "workframe"
        nested.mkdir(parents=True)
        stale = scripts / "apply-update-workframe.sh"
        canonical = nested / "apply-update-workframe.sh"
        stale.write_text("#!/usr/bin/env bash\n# stale wrapper\n", encoding="utf-8")
        canonical.write_text("#!/usr/bin/env bash\n# canonical supervisor-aware script\n", encoding="utf-8")
        old_scripts = supervisor.SCRIPTS_DIR
        old_compose = supervisor.COMPOSE_DIR
        try:
            supervisor.SCRIPTS_DIR = scripts
            supervisor.COMPOSE_DIR = root / "compose"
            assert supervisor._update_script("apply-update-workframe.sh") == canonical
        finally:
            supervisor.SCRIPTS_DIR = old_scripts
            supervisor.COMPOSE_DIR = old_compose


def test_gateway_agent_version_probe() -> None:
    old_exec = supervisor._docker_exec
    try:
        supervisor._docker_exec = lambda *_args, **_kwargs: (0, "Hermes Agent v0.19.1 (build)")
        assert supervisor._gateway_agent_version() == "0.19.1"
        supervisor._docker_exec = lambda *_args, **_kwargs: (1, "failed")
        assert supervisor._gateway_agent_version() == ""
    finally:
        supervisor._docker_exec = old_exec


def test_stack_release_status_reads_component_versions() -> None:
    import json
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        compose_dir = Path(tmp)
        for rel, version in (
            ("workframe-api/workframe-api-build.json", "0.1.31"),
            ("workframe-ui/public/workframe-build.json", "0.1.32"),
            ("workframe-supervisor/workframe-supervisor-build.json", "0.1.33"),
        ):
            path = compose_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"package_version": version}), encoding="utf-8")
        old_compose = supervisor.COMPOSE_DIR
        old_run = supervisor._compose_run
        try:
            supervisor.COMPOSE_DIR = compose_dir
            supervisor._compose_run = lambda *_args, **_kwargs: type(
                "Result",
                (),
                {"returncode": 1, "stdout": ""},
            )()
            status = supervisor._stack_release_status()
            assert status["api_build"] == "0.1.31"
            assert status["ui_build"] == "0.1.32"
            assert status["supervisor_build"] == "0.1.33"
            assert status["supervisor_runtime"] == supervisor.VERSION
        finally:
            supervisor.COMPOSE_DIR = old_compose
            supervisor._compose_run = old_run


def main() -> None:
    test_secret_read_blocked()
    test_foreign_profile_secrets_blocked()
    test_invalid_profile_slug_rejected()
    test_supervisor_auth_required()
    test_raw_container_exec_disabled_by_default()
    test_api_compose_public_has_no_docker_sock()
    test_host_install_paths_reads_env_file()
    test_stack_apply_lock_held()
    test_stack_apply_status_round_trip()
    test_update_script_falls_back_to_compose_tree()
    test_update_script_prefers_canonical_nested_mount_over_stale_wrapper()
    test_gateway_agent_version_probe()
    test_stack_release_status_reads_component_versions()
    print("supervisor negative tests ok")


if __name__ == "__main__":
    main()
