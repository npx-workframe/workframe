"""Install / stack wizard route handlers (WF-032 slice)."""

from __future__ import annotations

import base64
from typing import Any

import install_api
import site_meta
import stack_config
from supervisor_client import _maybe_sync_compose_public_url, _supervisor_ready, _supervisor_request


def _srv():
    import server

    return server


class InstallRoutesMixin:
    def _route_get_install_status(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        if install_api.install_window_open(str(srv._workframe_db_path())):
            try:
                srv._ensure_native_hermes_profile()
            except Exception:
                pass
        payload = install_api.install_status_payload(
            srv.DEPLOYMENT_MODE,
            srv.SECURE_MODE,
            srv.DEV_LOCAL_UNSAFE,
            str(srv._workframe_db_path()),
        )
        self._json(200, payload)

    def _route_get_install_stack(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        if not srv._install_window_open() and not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        payload = stack_config.public_stack_payload()
        payload["wizard"] = install_api.install_wizard_public_payload(str(srv._workframe_db_path()))
        self._json(200, {"ok": True, **payload})

    def _route_get_install_url_test(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        if not srv._install_window_open():
            self._json(403, {"ok": False, "error": "install_closed"})
            return
        url = (qs.get("url") or [""])[0] or stack_config.get_stack_config().get("app_base_url") or ""
        self._json(200, install_api.url_test(str(url)))

    def _route_get_install_publish_hints(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        if not srv._install_window_open():
            self._json(403, {"ok": False, "error": "install_closed"})
            return
        url = (qs.get("url") or [""])[0] or stack_config.get_stack_config().get("app_base_url") or ""
        self._json(200, install_api.publish_hints_payload(str(url)))

    def _route_post_install_email_test(self, body: dict) -> None:
        srv = _srv()
        if not srv._install_window_open():
            self._json(403, {"ok": False, "error": "install_closed"})
            return
        if not srv._install_owner_session_ok(self):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        try:
            to_email = str(body.get("email", "")).strip()
            result = install_api.smtp_test_send(to_email)
            self._json(200, result)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc), "hint": install_api.smtp_error_hint(exc)})
        except Exception as exc:
            self._json(500, {"ok": False, "error": str(exc), "hint": install_api.smtp_error_hint(exc)})

    def _route_post_install_url_test(self, body: dict) -> None:
        srv = _srv()
        if not srv._install_window_open():
            self._json(403, {"ok": False, "error": "install_closed"})
            return
        url = str(body.get("url") or body.get("app_base_url") or "").strip()
        self._json(200, install_api.url_test(url))

    def _route_post_install_setup_https(self, body: dict) -> None:
        srv = _srv()
        if not srv._install_window_open():
            self._json(403, {"ok": False, "error": "install_closed"})
            return
        try:
            host, port = install_api.normalize_setup_https(
                str(body.get("host") or body.get("url") or body.get("app_base_url") or ""),
                body.get("port"),
            )
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        if not _supervisor_ready():
            self._json(503, {"ok": False, "error": "supervisor_unavailable"})
            return
        status, data = _supervisor_request(
            "POST",
            "/v1/host.setup_public_https",
            {"host": host, "port": port},
            timeout=600.0,
        )
        if status < 400:
            sync = _maybe_sync_compose_public_url(f"https://{host}")
            if isinstance(data, dict) and sync:
                data = {**data, "compose_sync": sync}
        self._json(status, data if isinstance(data, dict) else {"ok": False, "error": "invalid_response"})

    def _route_post_install_complete(self, body: dict) -> None:
        srv = _srv()
        user_id = str(getattr(self, "auth_user", "") or "").strip()
        if not user_id and srv.DEPLOYMENT_MODE != "single_user_local":
            self._json(401, {"ok": False, "error": "no_session"})
            return
        self._json(200, self._complete_install(user_id, body))

    def _route_post_install_stack_branding_asset(self, body: dict) -> None:
        srv = _srv()
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        kind = str(body.get("kind") or "").strip().lower()
        if kind not in {"og", "favicon"}:
            self._json(400, {"ok": False, "error": "invalid_kind"})
            return
        raw_b64 = str(body.get("data_base64") or "").strip()
        if raw_b64.startswith("data:"):
            header, _, encoded = raw_b64.partition(",")
            content_type = header.split(";")[0].replace("data:", "").strip()
            raw_b64 = encoded
        else:
            content_type = str(body.get("content_type") or "").strip()
        try:
            data = base64.b64decode(raw_b64, validate=False)
        except Exception:
            self._json(400, {"ok": False, "error": "invalid_base64"})
            return
        try:
            site_meta.save_branding_asset(kind, data, content_type)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        meta = srv._public_site_meta_payload()
        self._json(
            200,
            {
                "ok": True,
                "kind": kind,
                "og_image": meta.get("og_image"),
                "favicon": meta.get("favicon"),
            },
        )

    def _route_patch_install_stack(self, body: dict) -> None:
        srv = _srv()
        if not srv._install_window_open() and not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        if not srv._install_owner_session_ok(self):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        try:
            updated = stack_config.patch_stack_config(body if isinstance(body, dict) else {})
            compose_sync = None
            if isinstance(body, dict) and body.get("app_base_url"):
                compose_sync = _maybe_sync_compose_public_url(str(body.get("app_base_url") or ""))
            srv.DEPLOYMENT_MODE = srv._resolve_deployment_mode()
            payload: dict[str, Any] = {"ok": True, **updated}
            if compose_sync is not None:
                payload["compose_sync"] = compose_sync
            self._json(200, payload)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
