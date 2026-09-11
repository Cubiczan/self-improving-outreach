"""Run tracing. Daytona SDK when present; otherwise structured in-process spans."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional, Protocol

from self_improving_outreach.config import Settings

logger = logging.getLogger("self_improving_outreach.trace")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunTracer(Protocol):
    def span(self, name: str, attributes: Optional[dict[str, Any]] = None) -> Any: ...

    def event(self, name: str, attributes: Optional[dict[str, Any]] = None) -> None: ...

    def records(self) -> list[dict[str, Any]]: ...


class LoggingTracer:
    """Always-on tracer. Spans are attached to agent_runs.traces."""

    def __init__(self, run_id: str = "") -> None:
        self.run_id = run_id
        self._records: list[dict[str, Any]] = []

    @contextmanager
    def span(self, name: str, attributes: Optional[dict[str, Any]] = None) -> Iterator[None]:
        started = _now()
        payload = {"name": name, "started_at": started, "attributes": attributes or {}}
        self._records.append({**payload, "phase": "start"})
        logger.info("span.start %s %s", name, attributes or {})
        try:
            yield
            self._records.append({"name": name, "phase": "ok", "finished_at": _now()})
        except Exception as exc:
            self._records.append(
                {
                    "name": name,
                    "phase": "error",
                    "finished_at": _now(),
                    "error": str(exc),
                }
            )
            raise

    def event(self, name: str, attributes: Optional[dict[str, Any]] = None) -> None:
        self._records.append(
            {"name": name, "phase": "event", "at": _now(), "attributes": attributes or {}}
        )
        logger.info("event %s %s", name, attributes or {})

    def records(self) -> list[dict[str, Any]]:
        return list(self._records)


class DaytonaTracer(LoggingTracer):
    """Wraps LoggingTracer and optionally boots the Daytona Python SDK.

    Documented usage (https://www.daytona.io/docs/en/python-sdk/sync/daytona/):

        from daytona import Daytona, DaytonaConfig
        config = DaytonaConfig(
            api_key=os.environ["DAYTONA_API_KEY"],
            api_url=os.environ.get("DAYTONA_API_URL", "https://app.daytona.io/api"),
            otel_enabled=True,  # or DAYTONA_OTEL_ENABLED=true
        )
        daytona = Daytona(config)
        # Optional: sandbox = daytona.create(); sandbox.process.code_run(...)

    This scaffold records OTEL-style spans locally and initializes the client
    when the SDK + API key are available. Creating a sandbox per crew run is
    gated by DAYTONA_SANDBOX_RUNS because it is not required for text drafts.
    """

    def __init__(self, settings: Settings, run_id: str = "") -> None:
        super().__init__(run_id=run_id)
        self.settings = settings
        self.client = None
        self.sandbox = None
        if settings.daytona_api_key:
            self._try_init()

    def _try_init(self) -> None:
        try:
            from daytona import Daytona, DaytonaConfig  # type: ignore
        except Exception:
            self.event("daytona.sdk_missing", {})
            return
        try:
            config = DaytonaConfig(
                api_key=self.settings.daytona_api_key,
                api_url=self.settings.daytona_api_url,
                otel_enabled=self.settings.daytona_otel_enabled,
            )
            self.client = Daytona(config)
            self.event("daytona.client_ready", {"api_url": self.settings.daytona_api_url})
            if self.settings.daytona_sandbox_runs:
                self.sandbox = self.client.create()
                self.event("daytona.sandbox_created", {})
        except Exception as exc:  # noqa: BLE001
            self.event("daytona.init_failed", {"error": str(exc)})

    def close(self) -> None:
        if self.sandbox is not None:
            try:
                self.sandbox.delete()
            except Exception as exc:  # noqa: BLE001
                logger.warning("daytona sandbox delete failed: %s", exc)
            self.sandbox = None


def build_tracer(settings: Settings, run_id: str = "") -> LoggingTracer:
    if settings.daytona_api_key:
        return DaytonaTracer(settings, run_id=run_id)
    return LoggingTracer(run_id=run_id)
