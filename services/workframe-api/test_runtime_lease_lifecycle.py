"""Regression: LLM broker credentials are runtime-scoped, not chat-turn scoped."""

from __future__ import annotations

from pathlib import Path

import credential_vault
import turn_credentials
import turn_overlay


class _ServerStub:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.restarts = 0

    def resolve_hermes_profile(self, profile: str) -> str:
        return profile

    def _read_model_from_config(self, _profile: str) -> tuple[str, str]:
        return "custom", "openrouter/auto"

    def _read_env_map(self, path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                key, sep, value = line.partition("=")
                if sep:
                    values[key] = value
        return values

    def _profile_dir(self, _profile: str) -> Path:
        path = self.root / "profile"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _read_model_block(self, _profile: str) -> dict[str, str]:
        path = self._profile_dir(_profile) / "model-key"
        return {"api_key": path.read_text(encoding="utf-8") if path.is_file() else ""}

    def _provider_env_var(self, _provider: str) -> str:
        return "OPENROUTER_API_KEY"

    def _is_runtime_profile_slug(self, _profile: str) -> bool:
        return True

    def _oauth_llm_provider_spec(self, _provider: str):
        return None

    def _upsert_env_secret(self, path: Path, key: str, value: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{key}={value}\n", encoding="utf-8")


def test_runtime_llm_lease_survives_chat_turn_cleanup(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "workframe.db"
    monkeypatch.setattr(turn_credentials, "WORKFRAME_DB", db_path)
    turn_credentials._SCHEMA_READY.clear()
    monkeypatch.setattr(credential_vault, "DATA_DIR", tmp_path)
    monkeypatch.setattr(credential_vault, "VAULT_DB", tmp_path / "credential_vault.db")
    credential_vault._SCHEMA_READY.clear()
    stub = _ServerStub(tmp_path)
    monkeypatch.setattr(turn_overlay, "_srv", lambda: stub)
    monkeypatch.setattr(
        turn_overlay,
        "_require_runtime_owner_provider",
        lambda *_args, **_kwargs: {"credential_binding_id": "binding-1"},
    )
    monkeypatch.setattr(turn_overlay, "_ensure_profile_llm_proxy", lambda *_args: None)

    def _sync(profile: str, token: str, *, wait_healthy: bool = False) -> None:
        (stub._profile_dir(profile) / "model-key").write_text(token, encoding="utf-8")
        if wait_healthy:
            stub.restarts += 1

    monkeypatch.setattr(turn_overlay, "_sync_profile_model_api_key", _sync)
    monkeypatch.setattr(turn_overlay, "_user_action_env_specs", lambda: [])

    token_a = turn_overlay._apply_turn_credential_lease(
        "u-user-agent", "user-1", "workspace-1", "openrouter", "turn-a",
    )
    token_b = turn_overlay._apply_turn_credential_lease(
        "u-user-agent", "user-1", "workspace-1", "openrouter", "turn-b",
    )

    assert token_a == token_b
    assert stub.restarts == 1
    lease = turn_credentials.validate_lease(token_a)
    assert lease and lease["run_id"].startswith("runtime-llm:")

    turn_overlay._revoke_turn_credential_lease("turn-b", "u-user-agent")
    assert turn_credentials.validate_lease(token_a)
    assert stub.restarts == 1
