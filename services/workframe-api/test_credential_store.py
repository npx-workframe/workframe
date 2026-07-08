"""WF-032 credential_store self-check."""

from __future__ import annotations

import sys
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


if __name__ == "__main__":
    test_quote_env_value()
    test_remove_env_secret_missing_file(Path("/tmp/wf-cred-store-check"))
    print("test_credential_store: ok")
