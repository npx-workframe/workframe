"""Public site metadata — OG tags, PWA manifest, link previews."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

import stack_config

DEFAULT_TITLE = "Workframe. A workspace for humans and persistent AI coworkers."
DEFAULT_SHORT_NAME = "Workframe"
DEFAULT_DESCRIPTION = "Communities exchange messages. Workframe teams exchange work."
DEFAULT_THEME_COLOR = "#79689D"
DEFAULT_OG_IMAGE = "/assets/branding/og-default.png"
DEFAULT_FAVICON = "/favicon.svg"
DEFAULT_APPLE_TOUCH_ICON = "/apple-touch-icon.png"

DEFAULT_PWA_ICONS = [
    {"src": "./favicon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
    {"src": "./icon-32.png", "sizes": "32x32", "type": "image/png", "purpose": "any"},
    {"src": "./icon-96.png", "sizes": "96x96", "type": "image/png", "purpose": "any"},
    {"src": "./icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
    {"src": "./icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
]

BRANDING_DIR_NAME = "site-branding"
OG_FILENAME = "og-image"
FAVICON_FILENAME = "favicon"

_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def branding_dir() -> Path:
    root = stack_config.DATA_DIR / BRANDING_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def _site_branding_raw() -> dict[str, Any]:
    raw = stack_config._read_raw()
    block = raw.get("site_branding")
    return block if isinstance(block, dict) else {}


def site_branding_public() -> dict[str, Any]:
    block = _site_branding_raw()
    return {
        "title": str(block.get("title") or "").strip(),
        "description": str(block.get("description") or "").strip(),
        "theme_color": str(block.get("theme_color") or "").strip(),
        "has_og_image": _branding_asset_path("og").is_file(),
        "has_favicon": _branding_asset_path("favicon").is_file(),
    }


def patch_site_branding(body: dict[str, Any]) -> None:
    raw = stack_config._read_raw()
    block = raw.get("site_branding") if isinstance(raw.get("site_branding"), dict) else {}
    for key in ("title", "description", "theme_color"):
        if key in body:
            block[key] = str(body.get(key) or "").strip()
    raw["site_branding"] = block
    stack_config._write_raw(raw)


def _branding_asset_path(kind: str) -> Path:
    block = _site_branding_raw()
    rel = str(block.get(f"{kind}_file") or "").strip()
    if rel:
        candidate = stack_config.DATA_DIR / rel
        if candidate.is_file():
            return candidate
    for suffix in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico"):
        candidate = branding_dir() / f"{OG_FILENAME if kind == 'og' else FAVICON_FILENAME}{suffix}"
        if candidate.is_file():
            return candidate
    return branding_dir() / f"{OG_FILENAME if kind == 'og' else FAVICON_FILENAME}.png"


def save_branding_asset(kind: str, data: bytes, content_type: str = "") -> Path:
    if kind not in {"og", "favicon"}:
        raise ValueError("invalid_branding_kind")
    if not data:
        raise ValueError("empty_asset")
    suffix = _suffix_for_upload(content_type, data)
    dest = branding_dir() / f"{OG_FILENAME if kind == 'og' else FAVICON_FILENAME}{suffix}"
    dest.write_bytes(data)
    raw = stack_config._read_raw()
    block = raw.get("site_branding") if isinstance(raw.get("site_branding"), dict) else {}
    block[f"{kind}_file"] = f"{BRANDING_DIR_NAME}/{dest.name}"
    raw["site_branding"] = block
    stack_config._write_raw(raw)
    return dest


def _suffix_for_upload(content_type: str, data: bytes) -> str:
    ctype = str(content_type or "").split(";")[0].strip().lower()
    if ctype == "image/png" or data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if ctype in {"image/jpeg", "image/jpg"} or data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if ctype == "image/webp" or data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if ctype == "image/svg+xml" or data.lstrip()[:5] == b"<svg " or b"<svg" in data[:200]:
        return ".svg"
    if ctype == "image/x-icon":
        return ".ico"
    return ".png"


def _abs_url(base: str, path: str) -> str:
    base = str(base or "").strip().rstrip("/")
    path = str(path or "").strip()
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not base:
        return path
    return urljoin(f"{base}/", path.lstrip("/"))


def _browser_asset_url(base: str, path: str) -> str:
    """Same-origin static assets — relative paths avoid loopback leaks on HTTPS deploys."""
    path = str(path or "").strip()
    if path.startswith("/") and not path.startswith("//"):
        return path
    return _abs_url(base, path)


def resolve_site_meta(
    *,
    app_base_url: str,
    install_complete: bool,
    workspace: dict[str, Any] | None = None,
    normalize_logo: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Merge stack overrides, primary workspace identity, and Workframe defaults."""
    overrides = _site_branding_raw()
    ws = workspace or {}

    title = str(overrides.get("title") or "").strip()
    if not title and install_complete:
        title = str(ws.get("display_name") or "").strip()
    if not title:
        title = DEFAULT_TITLE

    description = str(overrides.get("description") or "").strip()
    if not description and install_complete:
        description = str(ws.get("description") or "").strip()
    if not description:
        description = DEFAULT_DESCRIPTION

    tagline = str(ws.get("tagline") or "").strip() if install_complete else ""

    theme_color = str(overrides.get("theme_color") or "").strip() or DEFAULT_THEME_COLOR

    og_path = _branding_asset_path("og")
    if og_path.is_file():
        og_image = _browser_asset_url(app_base_url, f"/api/public/branding/og{og_path.suffix}")
    elif install_complete:
        logo = str(ws.get("avatar_url") or "").strip()
        if logo and normalize_logo:
            logo = normalize_logo(logo)
        og_image = _browser_asset_url(app_base_url, logo) if logo else _browser_asset_url(app_base_url, DEFAULT_OG_IMAGE)
    else:
        og_image = _browser_asset_url(app_base_url, DEFAULT_OG_IMAGE)

    fav_path = _branding_asset_path("favicon")
    if fav_path.is_file():
        favicon = _browser_asset_url(app_base_url, f"/api/public/branding/favicon{fav_path.suffix}")
        apple_touch = favicon
    else:
        favicon = _browser_asset_url(app_base_url, DEFAULT_FAVICON)
        apple_touch = _browser_asset_url(app_base_url, DEFAULT_APPLE_TOUCH_ICON)

    if title == DEFAULT_TITLE:
        short_name = DEFAULT_SHORT_NAME
    elif len(title) <= 16:
        short_name = title
    else:
        short_name = title[:15].rstrip() + "…"
    canonical = app_base_url.rstrip("/") + "/" if app_base_url else "/"

    return {
        "ok": True,
        "install_complete": bool(install_complete),
        "title": title,
        "short_name": short_name,
        "description": description,
        "tagline": tagline,
        "theme_color": theme_color,
        "og_image": og_image,
        "favicon": favicon,
        "apple_touch_icon": apple_touch,
        "canonical_url": canonical,
        "manifest_url": _browser_asset_url(app_base_url, "/manifest.webmanifest"),
        "source": {
            "title": "stack" if overrides.get("title") else ("workspace" if install_complete and ws.get("display_name") else "default"),
            "description": "stack" if overrides.get("description") else ("workspace" if install_complete and ws.get("description") else "default"),
            "og_image": "upload" if og_path.is_file() else ("workspace_logo" if install_complete and ws.get("avatar_url") else "default"),
            "favicon": "upload" if fav_path.is_file() else "default",
        },
    }


def manifest_payload(meta: dict[str, Any]) -> dict[str, Any]:
    favicon = str(meta.get("favicon") or "").strip()
    custom_icons = []
    if favicon and favicon != _browser_asset_url("", DEFAULT_FAVICON):
        custom_icons.append(
            {
                "src": favicon,
                "sizes": "any",
                "type": "image/svg+xml" if favicon.endswith(".svg") else "image/png",
                "purpose": "any",
            },
        )
    icons = custom_icons or DEFAULT_PWA_ICONS
    return {
        "name": meta.get("title") or DEFAULT_TITLE,
        "short_name": meta.get("short_name") or DEFAULT_SHORT_NAME,
        "description": meta.get("description") or DEFAULT_DESCRIPTION,
        "start_url": "./",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": meta.get("theme_color") or DEFAULT_THEME_COLOR,
        "orientation": "any",
        "icons": icons,
    }


def link_preview_html(meta: dict[str, Any]) -> str:
    title = _html_escape(str(meta.get("title") or DEFAULT_TITLE))
    description = _html_escape(str(meta.get("description") or DEFAULT_DESCRIPTION))
    canonical = _html_escape(str(meta.get("canonical_url") or "/"))
    og_image = _html_escape(str(meta.get("og_image") or ""))
    theme = _html_escape(str(meta.get("theme_color") or DEFAULT_THEME_COLOR))
    favicon = _html_escape(str(meta.get("favicon") or DEFAULT_FAVICON))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <meta name="description" content="{description}" />
  <meta name="theme-color" content="{theme}" />
  <link rel="icon" href="{favicon}" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="{title}" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{description}" />
  <meta property="og:url" content="{canonical}" />
  <meta property="og:image" content="{og_image}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{title}" />
  <meta name="twitter:description" content="{description}" />
  <meta name="twitter:image" content="{og_image}" />
  <meta http-equiv="refresh" content="0;url={canonical}" />
</head>
<body><p><a href="{canonical}">{title}</a></p></body>
</html>
"""


def branding_asset_bytes(kind: str) -> tuple[bytes, str] | None:
    path = _branding_asset_path(kind)
    if not path.is_file():
        return None
    ctype = _MIME_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")
    return path.read_bytes(), ctype


def _html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
