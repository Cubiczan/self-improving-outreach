"""Tool adapters.

You.com / One You / One Daytona are lazy so
``from self_improving_outreach.tools.one_daytona import ...`` does not pull
``you_com`` → ``stores.base`` → ``chp.session`` (OutreachStore circular import).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from self_improving_outreach.tools.one_cli import OneCli, OneError

__all__ = [
    "HttpYouComClient",
    "MockYouComClient",
    "OneCli",
    "OneDaytonaClient",
    "OneError",
    "OneSandbox",
    "OneYouComClient",
    "ResilientYouCom",
    "YouComError",
    "merge_sandbox_create_body",
]

_LAZY_ATTRS: dict[str, str] = {
    "HttpYouComClient": "self_improving_outreach.tools.you_com",
    "MockYouComClient": "self_improving_outreach.tools.you_com",
    "OneDaytonaClient": "self_improving_outreach.tools.one_daytona",
    "OneSandbox": "self_improving_outreach.tools.one_daytona",
    "OneYouComClient": "self_improving_outreach.tools.one_you",
    "ResilientYouCom": "self_improving_outreach.tools.you_com",
    "YouComError": "self_improving_outreach.tools.you_com",
    "merge_sandbox_create_body": "self_improving_outreach.tools.one_daytona",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_ATTRS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
