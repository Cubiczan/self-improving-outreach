"""You.com Search / Contents / Research wrapper with retry-then-cache failover."""

from __future__ import annotations

from typing import Any, Optional, Protocol

import httpx

from self_improving_outreach.models import Lead, ResearchBundle, Snippet, ToolFailure, new_id
from self_improving_outreach.observability.tracing import RunTracer
from self_improving_outreach.stores.base import OutreachStore

SEARCH_URL = "https://ydc-index.io/v1/search"
CONTENTS_URL = "https://ydc-index.io/v1/contents"
RESEARCH_URL = "https://api.you.com/v1/research"


class YouComError(Exception):
    """Raised when You.com HTTP or SDK calls fail."""


class YouSearcher(Protocol):
    def search(self, query: str, *, count: int = 5) -> ResearchBundle: ...

    def contents(self, urls: list[str]) -> ResearchBundle: ...

    def research(self, prompt: str) -> ResearchBundle: ...


class HttpYouComClient:
    """Direct HTTP client. Auth: X-API-Key from YOU_API_KEY / YDC_API_KEY.

    Current You.com surface (2026):
    - POST https://ydc-index.io/v1/search
    - POST https://ydc-index.io/v1/contents
    - POST https://api.you.com/v1/research
    Optional SDK: `from youdotcom import You` when extra `you` is installed.
    """

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "Content-Type": "application/json"}

    def search(self, query: str, *, count: int = 5) -> ResearchBundle:
        sdk_bundle = self._sdk_search(query, count)
        if sdk_bundle is not None:
            return sdk_bundle
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                SEARCH_URL,
                headers=self._headers(),
                json={"query": query, "count": count},
            )
            try:
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise YouComError(f"search failed: {exc}") from exc
            payload = response.json()
        return _bundle_from_search(query, payload)

    def contents(self, urls: list[str]) -> ResearchBundle:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                CONTENTS_URL,
                headers=self._headers(),
                json={"urls": urls, "formats": ["markdown"]},
            )
            try:
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise YouComError(f"contents failed: {exc}") from exc
            payload = response.json()
        snippets = []
        pages = payload if isinstance(payload, list) else payload.get("results") or payload.get("pages") or []
        for page in pages:
            snippets.append(
                Snippet(
                    title=page.get("title") or "",
                    url=page.get("url") or "",
                    text=(page.get("markdown") or page.get("html") or "")[:1500],
                )
            )
        return ResearchBundle(query=";".join(urls), snippets=snippets, source="you.com.contents")

    def research(self, prompt: str) -> ResearchBundle:
        with httpx.Client(timeout=max(self.timeout, 60.0)) as client:
            response = client.post(
                RESEARCH_URL,
                headers=self._headers(),
                json={"input": prompt, "research_effort": "lite"},
            )
            try:
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise YouComError(f"research failed: {exc}") from exc
            payload = response.json()
        answer = payload.get("answer") or payload.get("output") or payload.get("text") or ""
        sources = payload.get("sources") or []
        snippets = [
            Snippet(title=src.get("title") or "", url=src.get("url") or "", text=src.get("snippet") or "")
            for src in sources
            if isinstance(src, dict)
        ]
        return ResearchBundle(
            query=prompt,
            snippets=snippets,
            synthesis=str(answer)[:4000],
            source="you.com.research",
            raw=payload if isinstance(payload, dict) else {},
        )

    def _sdk_search(self, query: str, count: int) -> Optional[ResearchBundle]:
        try:
            from youdotcom import You  # type: ignore
        except Exception:
            return None
        try:
            with You(api_key_auth=self.api_key) as you:
                results = you.search.unified(query=query, count=count)
            snippets: list[Snippet] = []
            web = getattr(getattr(results, "results", None), "web", None) or []
            for item in web:
                snippets.append(
                    Snippet(
                        title=getattr(item, "title", "") or "",
                        url=getattr(item, "url", "") or "",
                        text=" ".join(getattr(item, "snippets", None) or [])[:1500],
                    )
                )
            return ResearchBundle(query=query, snippets=snippets, source="youdotcom.sdk")
        except Exception as exc:
            raise YouComError(f"youdotcom sdk search failed: {exc}") from exc


class MockYouComClient:
    """Deterministic live-web stand-in for CI and local swarm demos."""

    def __init__(self, fail_times: int = 0, fail_on_query: Optional[str] = None) -> None:
        self.fail_times = fail_times
        self.fail_on_query = fail_on_query
        self.calls = 0

    def search(self, query: str, *, count: int = 5) -> ResearchBundle:
        return self._maybe_fail(query, "search")

    def contents(self, urls: list[str]) -> ResearchBundle:
        return self._maybe_fail(";".join(urls), "contents")

    def research(self, prompt: str) -> ResearchBundle:
        return self._maybe_fail(prompt, "research")

    def _maybe_fail(self, query: str, kind: str) -> ResearchBundle:
        self.calls += 1
        if self.fail_times > 0:
            self.fail_times -= 1
            raise YouComError(f"mock {kind} failure")
        if self.fail_on_query and self.fail_on_query.lower() in query.lower():
            raise YouComError(f"mock {kind} failure for {self.fail_on_query}")
        return ResearchBundle(
            query=query,
            snippets=[
                Snippet(
                    title="Cubiczan-relevant finance signal",
                    url="https://cubiczan.com",
                    text=(
                        f"Mock {kind} for '{query}': CFO/CIO agenda around close, "
                        "reconciliation, SOX / material weakness, and treasury observability."
                    ),
                )
            ],
            synthesis=f"Mock You.com {kind} synthesis for {query}.",
            source="mock",
        )


def _bundle_from_search(query: str, payload: dict[str, Any]) -> ResearchBundle:
    snippets: list[Snippet] = []
    results = payload.get("results") or payload
    web = []
    if isinstance(results, dict):
        web = results.get("web") or results.get("hits") or []
        news = results.get("news") or []
        web = list(web) + list(news)
    elif isinstance(results, list):
        web = results
    for item in web:
        if not isinstance(item, dict):
            continue
        snippets.append(
            Snippet(
                title=item.get("title") or "",
                url=item.get("url") or item.get("link") or "",
                text=" ".join(item.get("snippets") or [item.get("description") or item.get("snippet") or ""])[:1500],
            )
        )
    return ResearchBundle(query=query, snippets=snippets, source="you.com.search", raw=payload)


class ResilientYouCom:
    """Retry You.com once, then degrade to cached lead context and log tool_failures."""

    def __init__(
        self,
        client: YouSearcher,
        store: OutreachStore,
        tracer: RunTracer,
        tool_name: str = "you.com",
    ) -> None:
        self.client = client
        self.store = store
        self.tracer = tracer
        self.tool_name = tool_name

    def refresh(self, lead: Lead, run_id: str) -> ResearchBundle:
        query = (
            f"{lead.company} {lead.contact_name} {lead.title} CFO CIO finance close "
            "reconciliation treasury SOX material weakness"
        )
        last_error: Optional[Exception] = None
        for attempt in (1, 2):
            try:
                with self.tracer.span("you.com.search", {"attempt": attempt, "lead_id": lead.lead_id}):
                    bundle = self.client.search(query)
                if bundle.as_text():
                    self.store.save_cached_context(lead.lead_id, bundle.as_text())
                return bundle
            except Exception as exc:  # noqa: BLE001 — failover must catch SDK/HTTP/mock
                last_error = exc
                degraded = attempt == 2
                self.store.log_tool_failure(
                    ToolFailure(
                        failure_id=new_id(),
                        run_id=run_id,
                        tool_name=self.tool_name,
                        error_class=type(exc).__name__,
                        message=str(exc),
                        retry_attempt=attempt,
                        degraded=degraded,
                    )
                )
                self.tracer.event(
                    "tool_failure",
                    {"tool": self.tool_name, "attempt": attempt, "error": str(exc)},
                )
        cached = self.store.cached_context(lead)
        synthesis = cached or (
            f"Degraded context for {lead.company}: title={lead.title}; "
            f"industry={lead.industry}; signals={lead.signals}"
        )
        return ResearchBundle(
            query=query,
            snippets=[Snippet(title="cached_context", text=synthesis)],
            synthesis=synthesis,
            source="cache",
            degraded=True,
            raw={"error": str(last_error) if last_error else ""},
        )
