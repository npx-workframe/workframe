"""Handler route mixins extracted from server.Handler (WF-032)."""

from handler_modules.handler_chat import ChatRoutesMixin
from handler_modules.handler_install import InstallRoutesMixin

__all__ = ["ChatRoutesMixin", "InstallRoutesMixin"]
