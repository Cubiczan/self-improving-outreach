"""You.com Search / Contents / Research via One ``you`` actions."""

from __future__ import annotations

from typing import Any, Optional

from self_improving_outreach.models import ResearchBundle
from self_improving_outreach.tools.one_cli import (
    DEFAULT_YOU_RESEARCH_ACTION_ID,
    DEFAULT_YOU_SEARCH_ACTION_ID,
    YOU_PLATFORM,
    OneCli,
    OneError,
    unwrap_one_response,
)
from self_improving_outreach.tools.you_com import (
    YouComError,
    bundle_from_contents,
    bundle_from_research,
    bundle_from_search,
)


class OneYouComClient:
    """YouSearcher backed by ``one --agent actions execute you …``."""

    def __init__(
        self,
        connection_key: str,
        *,
        runner: Optional[OneCli] = None,
        search_action_id: str = DEFAULT_YOU_SEARCH_ACTION_ID,
        research_action_id: str = DEFAULT_YOU_RESEARCH_ACTION_ID,
        contents_action_id: Optional[str] = None,
        timeout: float = 90.0,
    ) -> None:
        if not connection_key:
            raise YouComError("ONE_YOU_CONNECTION_KEY is required for One research")
        self.connection_key = connection_key
        self.runner = runner or OneCli(timeout=timeout)
        self.search_action_id = search_action_id
        self.research_action_id = research_action_id
        self.contents_action_id = contents_action_id

    def _execute(self, action_id: str, data: dict[str, Any], *, timeout: Optional[float] = None) -> Any:
        try:
            payload = self.runner.execute(
                YOU_PLATFORM,
                action_id,
                self.connection_key,
                data=data,
                timeout=timeout,
            )
        except OneError as exc:
            raise YouComError(str(exc)) from exc
        unwrapped = unwrap_one_response(payload)
        return unwrapped if isinstance(unwrapped, dict) else payload

    def search(self, query: str, *, count: int = 5) -> ResearchBundle:
        body = self._execute(self.search_action_id, {"query": query, "count": count})
        if not isinstance(body, dict):
            body = {"results": body}
        return bundle_from_search(query, body, source="one.you.search")

    def contents(self, urls: list[str]) -> ResearchBundle:
        action_id = self.contents_action_id
        if not action_id:
            try:
                action_id = self.runner.resolve_action_id(YOU_PLATFORM, "contents extract urls")
            except OneError as exc:
                raise YouComError("One you contents action is not configured") from exc
        body = self._execute(action_id, {"urls": urls, "formats": ["markdown"]})
        return bundle_from_contents(urls, body, source="one.you.contents")

    def research(self, prompt: str) -> ResearchBundle:
        body = self._execute(
            self.research_action_id,
            {"input": prompt, "research_effort": "lite"},
            timeout=max(self.runner.timeout, 60.0),
        )
        if not isinstance(body, dict):
            body = {"output": str(body)}
        return bundle_from_research(prompt, body, source="one.you.research")
