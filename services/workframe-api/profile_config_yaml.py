"""Single write path for Hermes profile config.yaml model surface (WF-033).

Read path stays in server._parse_model_block_from_disk (text scan, no import cycle).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _load_cfg(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {}


def update_model_surface(
    config_path: Path,
    *,
    default: str | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    fallback_chain: list[dict[str, str]] | None = None,
    strip_proxy_fields: bool = False,
) -> None:
    """Merge model + fallback_providers keys; preserve other top-level yaml keys."""
    cfg = _load_cfg(config_path)
    model = cfg.get("model")
    if not isinstance(model, dict):
        model = {}
    if default is not None:
        model["default"] = default
    if provider is not None:
        model["provider"] = provider
    if base_url is not None:
        if base_url:
            model["base_url"] = base_url
        else:
            model.pop("base_url", None)
    if strip_proxy_fields:
        model.pop("api_key", None)
        model.pop("base_url", None)
    if model:
        cfg["model"] = model
    if fallback_chain is not None:
        rows = [
            {"provider": str(e.get("provider", "")).strip(), "model": str(e.get("model", "")).strip()}
            for e in fallback_chain
            if isinstance(e, dict) and str(e.get("provider", "")).strip() and str(e.get("model", "")).strip()
        ]
        if rows:
            cfg["fallback_providers"] = rows
        else:
            cfg.pop("fallback_providers", None)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
