"""Run tracing. Daytona SDK when present; otherwise structured in-process spans."""

from __future__ import annotations

import logging
import os
import socket
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional, Protocol
from urllib.parse import urlparse

from self_improving_outreach.config import Settings

logger = logging.getLogger("self_improving_outreach.trace")

_DEFAULT_OTLP_ENDPOINT = "http://localhost:4318"
_OTLP_PROBE_TIMEOUT_SECONDS = 0.2
_OTLP_EXPORT_TIMEOUT_MS = "1000"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _otlp_endpoint() -> str:
    return (os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or _DEFAULT_OTLP_ENDPOINT).strip()


def _otlp_host_port(endpoint: str) -> Optional[tuple[str, int]]:
    raw = endpoint.strip()
    if not raw:
        return None
    parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    host = parsed.hostname
    if not host:
        return None
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 4318
    return host, port


def _is_loopback_host(host: str) -> bool:
    return host.lower() in {"localhost", "127.0.0.1", "::1"}


def _otlp_loopback_reachable(endpoint: str) -> bool:
    parsed = _otlp_host_port(endpoint)
    if parsed is None:
        return False
    host, port = parsed
    if not _is_loopback_host(host):
        return True
    try:
        with socket.create_connection((host, port), timeout=_OTLP_PROBE_TIMEOUT_SECONDS):
            return True
    except OSError:
        return False


def _soften_otel_export_timeout() -> None:
    os.environ.setdefault("OTEL_EXPORTER_OTLP_TIMEOUT", _OTLP_EXPORT_TIMEOUT_MS)


def resolve_daytona_otel_enabled(settings: Settings) -> tuple[bool, Optional[str]]:
    """Return (enabled, degrade_reason). Local spans always stay on LoggingTracer."""
    if not settings.daytona_otel_enabled:
        return False, None
    endpoint = _otlp_endpoint()
    if not _otlp_loopback_reachable(endpoint):
        return False, "otlp_endpoint_unreachable"
    _soften_otel_export_timeout()
    return True, None


def _sandbox_name(run_id: str) -> str:
    return f"cubiczan-outreach-{run_id[:8]}" if run_id else "cubiczan-outreach"


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
            target=os.environ.get("DAYTONA_TARGET"),  # or DAYTONA_REGION; e.g. "us"
            otel_enabled=True,  # or DAYTONA_OTEL_ENABLED=true
        )
        daytona = Daytona(config)
        # Optional: sandbox = daytona.create(); sandbox.process.code_run(...)

    This scaffold records OTEL-style spans locally. Sandbox create prefers One
    ``daytona`` actions when ``SANDBOX_PROVIDER`` resolves to ``one``; otherwise
    it initializes the Daytona SDK when the API key is available. Creating a
    sandbox per crew run is gated by DAYTONA_SANDBOX_RUNS.

    SDK create needs an org default region in the Daytona Dashboard **or**
    ``DAYTONA_TARGET`` / ``DAYTONA_REGION`` (``DaytonaConfig.target``).
    """

    def __init__(self, settings: Settings, run_id: str = "", *, one_client=None) -> None:
        super().__init__(run_id=run_id)
        self.settings = settings
        self.client = None
        self.sandbox = None
        provider = settings.effective_sandbox_provider
        if provider == "one":
            self._try_init_one(one_client)
        elif provider == "daytona" or settings.daytona_api_key:
            self._try_init()

    def _try_init_one(self, one_client=None) -> None:
        try:
            from self_improving_outreach.tools.one_daytona import one_daytona_from_settings

            self.client = one_client or one_daytona_from_settings(self.settings)
            self.event("daytona.client_ready", {"provider": "one"})
            if self.settings.daytona_sandbox_runs:
                name = _sandbox_name(self.run_id)
                self.sandbox = self.client.create({"name": name})
                sandbox_id = getattr(self.sandbox, "id", "")
                self.event("daytona.sandbox_created", {"provider": "one", "sandbox_id": sandbox_id})
        except Exception as exc:  # noqa: BLE001
            self.event("daytona.init_failed", {"provider": "one", "error": str(exc)})

    def _try_init(self) -> None:
        try:
            from daytona import Daytona, DaytonaConfig  # type: ignore
        except Exception:
            self.event("daytona.sdk_missing", {})
            return
        otel_enabled, otel_reason = resolve_daytona_otel_enabled(self.settings)
        if otel_reason:
            self.event("daytona.otel_disabled", {"reason": otel_reason})
        try:
            config_kwargs: dict[str, Any] = {
                "api_key": self.settings.daytona_api_key,
                "api_url": self.settings.daytona_api_url,
                "otel_enabled": otel_enabled,
            }
            target = self.settings.resolved_daytona_target
            if target:
                config_kwargs["target"] = target
            config = DaytonaConfig(**config_kwargs)
            self.client = Daytona(config)
            ready_attrs: dict[str, Any] = {
                "api_url": self.settings.daytona_api_url,
                "provider": "daytona",
            }
            if target:
                ready_attrs["target"] = target
            self.event("daytona.client_ready", ready_attrs)
            if self.settings.daytona_sandbox_runs:
                self.sandbox = self._sdk_create(name=_sandbox_name(self.run_id), target=target)
                created_attrs: dict[str, Any] = {"provider": "daytona"}
                sandbox_id = getattr(self.sandbox, "id", "")
                if sandbox_id:
                    created_attrs["sandbox_id"] = sandbox_id
                if target:
                    created_attrs["target"] = target
                self.event("daytona.sandbox_created", created_attrs)
        except Exception as exc:  # noqa: BLE001
            self.event("daytona.init_failed", {"provider": "daytona", "error": str(exc)})

    def _sdk_create(self, *, name: str, target: Optional[str]) -> Any:
        params = _sdk_create_params(name=name, target=target)
        if params is not None:
            return self.client.create(params)
        return self.client.create()

    def close(self) -> None:
        if self.sandbox is not None:
            try:
                self.sandbox.delete()
            except Exception as exc:  # noqa: BLE001
                logger.warning("daytona sandbox delete failed: %s", exc)
            self.sandbox = None
        client = self.client
        closer = getattr(client, "close", None) if client is not None else None
        if callable(closer):
            try:
                closer()
            except Exception as exc:  # noqa: BLE001
                logger.warning("daytona client close failed: %s", exc)


def _sdk_create_params(*, name: str, target: Optional[str]) -> Any:
    try:
        from daytona import CreateSandboxFromSnapshotParams  # type: ignore
    except Exception:
        return None
    kwargs: dict[str, Any] = {"name": name}
    fields = getattr(CreateSandboxFromSnapshotParams, "model_fields", None)
    if fields is None:
        fields = getattr(CreateSandboxFromSnapshotParams, "__annotations__", {})
    if target and "target" in fields:
        kwargs["target"] = target
    try:
        return CreateSandboxFromSnapshotParams(**kwargs)
    except Exception:
        return None


def build_tracer(settings: Settings, run_id: str = "") -> LoggingTracer:
    if settings.effective_sandbox_provider != "none" or settings.daytona_api_key:
        return DaytonaTracer(settings, run_id=run_id)
    return LoggingTracer(run_id=run_id)
