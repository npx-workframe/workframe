"""Hermes named-profile session auth uses .env API_SERVER_KEY, not the yaml placeholder."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import profile_gateway as pg  # noqa: E402


class _Fake:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _profile_dir(self, profile: str) -> Path:
        return self.root / profile

    def _read_env_map(self, env_path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        if not env_path.is_file():
            return values
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.strip().startswith("#") or "=" not in line:
                continue
            key, _sep, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and value:
                values[key] = value
        return values

    def _profile_gateway_config_path(self, profile: str) -> Path:
        return self._profile_dir(profile) / "config.yaml"

    def _upsert_env_secret(self, env_path: Path, key: str, value: str) -> None:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text(f"{key}={value}\n", encoding="utf-8")


def test_profile_api_key_prefers_env_over_yaml_placeholder(tmp_path: Path) -> None:
    prof = "u-owner-mybusiness-agent"
    home = tmp_path / prof
    home.mkdir()
    (home / ".env").write_text("API_SERVER_KEY=real-env-secret-32bytes-long-key\n", encoding="utf-8")
    (home / "config.yaml").write_text(
        "platforms:\n  api_server:\n    extra:\n      key: workframe-local-key\n",
        encoding="utf-8",
    )
    fake = _Fake(tmp_path)
    orig = pg._srv
    pg._srv = lambda: fake  # type: ignore[assignment]
    try:
        assert pg._profile_api_key(prof) == "real-env-secret-32bytes-long-key"
        extra: dict = {}
        out = pg._ensure_profile_api_server_key(prof, extra)
        assert out == "real-env-secret-32bytes-long-key"
        assert extra["key"] == "real-env-secret-32bytes-long-key"
    finally:
        pg._srv = orig


def test_profile_api_key_falls_back_to_placeholder(tmp_path: Path) -> None:
    fake = _Fake(tmp_path)
    orig = pg._srv
    pg._srv = lambda: fake  # type: ignore[assignment]
    try:
        assert pg._profile_api_key("missing-profile") == "workframe-local-key"
    finally:
        pg._srv = orig
