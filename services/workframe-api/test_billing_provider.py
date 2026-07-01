"""ponytail self-check: billing provider source of truth = proxy URL, never model-id prefix.

Run: python services/workframe-api/test_billing_provider.py
No framework, no fixtures. Fails fast if the inference regression returns.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402  (module import is side-effect-free; main() is guarded)

# The bug case: profile model is google/gemini-2.5-flash but proxy routes via openrouter.
# The model-id prefix MUST NOT leak as the billing provider.
assert server._billing_provider_from_block("/internal/llm/openrouter/v1", "custom", "") == "openrouter", \
    "proxy URL segment must win over model-id prefix"
# Explicit hint honored.
assert server._billing_provider_from_block("", "", "anthropic") == "anthropic", "hint honored"
# Empty block defaults to openrouter (no inference).
assert server._billing_provider_from_block("", "", "") == "openrouter", "empty-block default"
# cfg_provider honored only when no proxy URL is set.
assert server._billing_provider_from_block("", "openai", "") == "openai", "cfg_provider honored without proxy"

print("billing provider self-check ok")
