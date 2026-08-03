"""WF-032 credential_store self-check."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import credential_store  # noqa: E402


def test_quote_env_value() -> None:
    assert credential_store._quote_env_value("sk-abc123") == "sk-abc123"
    assert credential_store._quote_env_value('has "quotes"') == '"has \\"quotes\\""'


def test_remove_env_secret_missing_file(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    credential_store._remove_env_secret(path, "OPENROUTER_API_KEY")
    assert not path.exists()


def test_auth_metadata_corruption_is_visible_and_preserved(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "auth.json"
    path.write_text("{not-json\n", encoding="utf-8")
    try:
        credential_store._upsert_auth_metadata(
            path,
            {"credential_ref": "vault:test", "provider": "openrouter", "credential_type": "api_key"},
        )
    except ValueError as exc:
        assert str(exc) == "auth_metadata_corrupt"
    else:
        raise AssertionError("corrupt auth metadata must fail visibly")
    assert path.read_text(encoding="utf-8") == "{not-json\n"


if __name__ == "__main__":
    test_quote_env_value()
    test_remove_env_secret_missing_file(Path("/tmp/wf-cred-store-check"))
    test_auth_metadata_corruption_is_visible_and_preserved(Path(tempfile.mkdtemp(prefix="wf-cred-store-check-")))
    print("test_credential_store: ok")
