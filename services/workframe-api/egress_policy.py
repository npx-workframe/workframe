"""Egress policy helpers — brokered provider hosts and forced-broker flag."""

from __future__ import annotations

import os

# Hostnames agents must not reach directly when WORKFRAME_FORCE_AGENT_EGRESS_BROKER=true.
BROKERED_PROVIDER_HOSTS: tuple[str, ...] = (
    "openrouter.ai",
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.deepseek.com",
    "api.github.com",
    "api.vercel.com",
    "api.netlify.com",
)

BROKER_API_HOST_ENV = "WORKFRAME_API_HOST"
FORCE_BROKER_ENV = "WORKFRAME_FORCE_AGENT_EGRESS_BROKER"
EGRESS_GUARD_SERVICE = "gateway-egress-guard"


def force_egress_broker_enabled() -> bool:
    raw = str(os.environ.get(FORCE_BROKER_ENV) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def broker_api_host() -> str:
    return str(os.environ.get(BROKER_API_HOST_ENV) or "workframe-api").strip() or "workframe-api"


def brokered_hosts_csv() -> str:
    return " ".join(BROKERED_PROVIDER_HOSTS)


if __name__ == "__main__":
    assert "openrouter.ai" in BROKERED_PROVIDER_HOSTS
    assert not force_egress_broker_enabled()
    os.environ[FORCE_BROKER_ENV] = "true"
    assert force_egress_broker_enabled()
    print("egress_policy ok")
