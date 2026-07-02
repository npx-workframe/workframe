"""ponytail: connected providers → model offers → billing alignment.

Run: python services/workframe-api/test_provider_model_surface.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402

codex_rows = server._model_catalog_rows_for_provider("codex")
codex_models = {row["model"] for row in codex_rows}
assert "gpt-5.4-medium" in codex_models, codex_models
assert "gpt-5.4-mini" in codex_models, codex_models
assert all("gemini" not in m for m in codex_models)

assert server._resolve_billing_provider_for_model("gpt-5.4-mini", {"codex"}) == "codex"
assert server._resolve_billing_provider_for_model("google/gemini-2.5-flash", {"codex"}) == ""
assert server._resolve_billing_provider_for_model(
    "google/gemini-2.5-flash", {"openrouter"}
) == "openrouter"

stack = server._suggestions_for_connected_llm_providers({"codex", "openrouter"})
models = {row["model"] for row in stack}
assert "gpt-5.4-medium" in models
assert any(m.startswith("google/") for m in models)

assert server._billing_provider_id_from_hermes_config("openai-codex") == "codex"

print("provider model surface self-check ok")
