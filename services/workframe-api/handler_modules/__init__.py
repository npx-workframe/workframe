"""Handler route mixins extracted from server.Handler (WF-032)."""

from handler_modules.handler_admin import AdminRoutesMixin
from handler_modules.handler_auth import AuthRoutesMixin
from handler_modules.handler_chat import ChatRoutesMixin
from handler_modules.handler_install import InstallRoutesMixin
from handler_modules.handler_provider import ProviderRoutesMixin
from handler_modules.handler_workspace import WorkspaceRoutesMixin

__all__ = [
    "AdminRoutesMixin",
    "AuthRoutesMixin",
    "ChatRoutesMixin",
    "InstallRoutesMixin",
    "ProviderRoutesMixin",
    "WorkspaceRoutesMixin",
]
