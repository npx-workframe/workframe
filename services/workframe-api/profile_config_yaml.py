"""Single write path for Hermes profile config.yaml model surface (WF-033).

Read path stays in server._parse_model_block_from_disk (text scan, no import cycle).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _salvage_top_level_keys(text: str) -> dict[str, Any]:
    """Keep non-model keys when safe_load cannot parse corrupt yaml (wizard duplicates)."""
    out: dict[str, Any] = {}
    skip = {"model", "fallback_providers"}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or line.startswith((" ", "\t")):
            i += 1
            continue
        if ":" not in stripped:
            i += 1
            continue
        key = stripped.split(":", 1)[0].strip()
        if key in skip:
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith((" ", "\t", "#"))):
                i += 1
            continue
        after = stripped.split(":", 1)[1].strip()
        if after:
            try:
                out[key] = yaml.safe_load(after)
            except yaml.YAMLError:
                out[key] = after.strip().strip("'\"")
            i += 1
            continue
        block = [line]
        i += 1
        while i < len(lines) and (not lines[i].strip() or lines[i].startswith((" ", "\t", "#"))):
            block.append(lines[i])
            i += 1
        try:
            frag = yaml.safe_load("\n".join(block))
            if isinstance(frag, dict) and key in frag:
                out[key] = frag[key]
            else:
                out[key] = None
        except yaml.YAMLError:
            out[key] = None
    return out


def _load_cfg(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return _salvage_top_level_keys(text)
    return data if isinstance(data, dict) else {}


def update_model_surface(
    config_path: Path,
    *,
    default: str | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    fallback_chain: list[dict[str, str]] | None = None,
    strip_proxy_fields: bool = False,
    coalesce: bool = False,
) -> None:
    """Merge model + fallback_providers keys; preserve other top-level yaml keys.

  ponytail: comments are not preserved (safe_load/safe_dump); read path uses text scan.
  coalesce=True drops duplicate model:/fallback_providers: blocks before rewrite.
    """
    cfg = _load_cfg(config_path)
    if coalesce:
        cfg.pop("model", None)
        cfg.pop("fallback_providers", None)
        model: dict[str, Any] = {}
    else:
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
    if api_key is not None:
        if api_key:
            model["api_key"] = api_key
        else:
            model.pop("api_key", None)
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
