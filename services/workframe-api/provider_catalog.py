"""WF-032 extract: curated provider connect catalog and lookups."""

from __future__ import annotations

from typing import Any

# ponytail: curated Hermes-native provider list; env vars match configuration docs.
PROVIDER_CONNECT_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "id": "openrouter",
        "label": "OpenRouter",
        "category": "llm",
        "connect_mode": "api_key",
        "env_var": "OPENROUTER_API_KEY",
        "description": "Primary LLM router — any model via one API key.",
    },
    {
        "id": "anthropic",
        "label": "Anthropic",
        "category": "llm",
        "connect_mode": "api_key",
        "env_var": "ANTHROPIC_API_KEY",
        "description": "Direct Claude API access.",
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "category": "llm",
        "connect_mode": "api_key",
        "env_var": "OPENAI_API_KEY",
        "description": "Direct OpenAI API access.",
    },
    {
        "id": "codex",
        "label": "OpenAI Codex",
        "category": "llm",
        "connect_mode": "oauth",
        "hermes_auth_id": "openai-codex",
        "description": "Codex CLI OAuth session (hermes auth add openai-codex).",
    },
    {
        "id": "google",
        "label": "Google Gemini",
        "category": "llm",
        "connect_mode": "api_key",
        "env_var": "GEMINI_API_KEY",
        "description": "Gemini models via API key.",
    },
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "category": "llm",
        "connect_mode": "api_key",
        "env_var": "DEEPSEEK_API_KEY",
        "description": "DeepSeek chat models.",
    },
    {
        "id": "brave",
        "label": "Brave Search",
        "category": "search",
        "connect_mode": "api_key",
        "env_var": "BRAVE_API_KEY",
        "description": "Web search API for agent tools.",
    },
    {
        "id": "nous",
        "label": "Nous Portal",
        "category": "llm",
        "connect_mode": "oauth",
        "hermes_auth_id": "nous",
        "description": "OAuth bundle for models + tool gateway (hermes setup --portal).",
    },
    {
        "id": "discord",
        "label": "Discord",
        "category": "messaging",
        "connect_mode": "bot_token",
        "env_var": "DISCORD_BOT_TOKEN",
        "description": "Bot token from the Discord Developer Portal.",
    },
    {
        "id": "telegram",
        "label": "Telegram",
        "category": "messaging",
        "connect_mode": "bot_token",
        "env_var": "TELEGRAM_BOT_TOKEN",
        "description": "Bot token from @BotFather.",
    },
    {
        "id": "slack",
        "label": "Slack",
        "category": "messaging",
        "connect_mode": "bot_token",
        "env_var": "SLACK_BOT_TOKEN",
        "extra_env_vars": ("SLACK_APP_TOKEN",),
        "description": "Slack bot + app tokens (Socket Mode).",
    },
    {
        "id": "github",
        "label": "GitHub",
        "category": "dev",
        "connect_mode": "oauth",
        "env_var": "GITHUB_TOKEN",
        "oauth_provider": "github",
        "hermes_auth_id": "github",
        "user_only": True,
        "description": "OAuth (admin registers app) or fine-grained PAT — repo push and GitHub API.",
    },
    {
        "id": "stripe",
        "label": "Stripe",
        "category": "payments",
        "connect_mode": "oauth",
        "env_var": "STRIPE_SECRET_KEY",
        "oauth_provider": "stripe",
        "user_only": True,
        "description": "Connect your Stripe account — charges, customers, and billing tools.",
    },
    {
        "id": "vercel",
        "label": "Vercel",
        "category": "dev",
        "connect_mode": "api_key",
        "env_var": "VERCEL_TOKEN",
        "user_only": True,
        "description": "Personal access token (VERCEL_TOKEN) for deploy/CLI tools.",
    },
    {
        "id": "netlify",
        "label": "Netlify",
        "category": "dev",
        "connect_mode": "api_key",
        "env_var": "NETLIFY_AUTH_TOKEN",
        "user_only": True,
        "description": "Netlify personal access token (NETLIFY_AUTH_TOKEN).",
    },
)

# Providers where agent actions must use the triggering user's credential only.
_USER_ONLY_PROVIDER_IDS: frozenset[str] = frozenset(
    str(spec["id"]).lower()
    for spec in PROVIDER_CONNECT_CATALOG
    if spec.get("user_only")
)


def catalog_provider(provider_id: str) -> dict[str, Any] | None:
    needle = str(provider_id or "").strip().lower()
    for row in PROVIDER_CONNECT_CATALOG:
        if str(row.get("id", "")).lower() == needle:
            return row
    return None


def catalog_provider_for_llm(llm_provider: str) -> dict[str, Any] | None:
    spec = catalog_provider(llm_provider)
    if spec:
        return spec
    needle = str(llm_provider or "").strip().lower()
    for row in PROVIDER_CONNECT_CATALOG:
        auth_id = str(row.get("hermes_auth_id") or row.get("id") or "").strip().lower()
        if auth_id == needle:
            return row
    return None


def provider_user_only(provider_id: str) -> bool:
    return str(provider_id or "").strip().lower() in _USER_ONLY_PROVIDER_IDS


def provider_env_vars(spec: dict[str, Any]) -> list[str]:
    names: list[str] = []
    primary = str(spec.get("env_var") or "").strip()
    if primary:
        names.append(primary)
    for extra in spec.get("extra_env_vars") or ():
        key = str(extra or "").strip()
        if key and key not in names:
            names.append(key)
    return names
