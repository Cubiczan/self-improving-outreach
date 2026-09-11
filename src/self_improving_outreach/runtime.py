"""Compose store, You.com, tracer, pipeline, and swarm from settings."""

from __future__ import annotations

from typing import Optional

from self_improving_outreach.config import Settings, get_settings
from self_improving_outreach.crews.pipeline import OutreachPipeline
from self_improving_outreach.observability.tracing import LoggingTracer, build_tracer
from self_improving_outreach.paths import sample_queue_path
from self_improving_outreach.stores.clickhouse import build_store
from self_improving_outreach.swarm.orchestrator import SwarmOrchestrator
from self_improving_outreach.swarm.queue import JsonLeadQueue, StoreLeadQueue
from self_improving_outreach.tools.you_com import HttpYouComClient, MockYouComClient, ResilientYouCom

SAMPLE_QUEUE = sample_queue_path()


def build_you_client(settings: Settings, mock: Optional[MockYouComClient] = None):
    if mock is not None:
        return mock
    if settings.is_mock or not settings.you_key:
        return MockYouComClient()
    return HttpYouComClient(api_key=settings.you_key)


def build_runtime(
    settings: Optional[Settings] = None,
    *,
    you_client=None,
    store=None,
    tracer: Optional[LoggingTracer] = None,
):
    settings = settings or get_settings()
    store = store or build_store(settings)
    tracer = tracer or build_tracer(settings)
    client = you_client or build_you_client(settings)
    you = ResilientYouCom(client, store, tracer)

    def pipeline_factory() -> OutreachPipeline:
        return OutreachPipeline(settings, store, you, tracer)

    return {
        "settings": settings,
        "store": store,
        "tracer": tracer,
        "you": you,
        "pipeline": pipeline_factory(),
        "pipeline_factory": pipeline_factory,
    }


def build_swarm(
    settings: Optional[Settings] = None,
    *,
    concurrency: Optional[int] = None,
    queue_path: Optional[str] = None,
    you_client=None,
    store=None,
) -> SwarmOrchestrator:
    runtime = build_runtime(settings, you_client=you_client, store=store)
    settings = runtime["settings"]
    store = runtime["store"]
    path = queue_path or (str(SAMPLE_QUEUE) if settings.is_mock and SAMPLE_QUEUE.exists() else None)
    queue: StoreLeadQueue
    if path:
        queue = JsonLeadQueue(store, path)
    else:
        queue = StoreLeadQueue(store)
    return SwarmOrchestrator(
        store=store,
        pipeline_factory=runtime["pipeline_factory"],
        tracer=runtime["tracer"],
        concurrency=concurrency or settings.swarm_concurrency,
        queue=queue,
    )
