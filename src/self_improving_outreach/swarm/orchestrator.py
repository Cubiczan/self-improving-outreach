"""Parallel closed-loop crews over a lead queue. Worker failures do not kill the swarm."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from self_improving_outreach.crews.pipeline import OutreachPipeline
from self_improving_outreach.models import PipelineResult, SwarmReport, new_id
from self_improving_outreach.observability.tracing import RunTracer
from self_improving_outreach.stores.base import OutreachStore
from self_improving_outreach.swarm.queue import StoreLeadQueue

logger = logging.getLogger(__name__)


class SwarmOrchestrator:
    def __init__(
        self,
        store: OutreachStore,
        pipeline_factory,
        tracer: RunTracer,
        concurrency: int = 5,
        queue: Optional[StoreLeadQueue] = None,
    ) -> None:
        self.store = store
        self.pipeline_factory = pipeline_factory
        self.tracer = tracer
        self.concurrency = max(1, concurrency)
        self.queue = queue or StoreLeadQueue(store)

    def run_once(self, *, max_leads: Optional[int] = None) -> SwarmReport:
        swarm_id = new_id()
        limit = max_leads if max_leads is not None else max(self.concurrency * 4, self.concurrency)
        leads = self.queue.claim(limit)
        report = SwarmReport(swarm_id=swarm_id)
        if not leads:
            report.weights_after = self.store.get_weights()
            report.top_patterns = [p.pattern_id for p in self.store.list_patterns()[:3]]
            return report

        with self.tracer.span("swarm.batch", {"swarm_id": swarm_id, "n": len(leads)}):
            with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
                futures = {
                    pool.submit(self._safe_run, lead, swarm_id, index): lead
                    for index, lead in enumerate(leads)
                }
                for future in as_completed(futures):
                    lead = futures[future]
                    try:
                        result = future.result()
                    except Exception as exc:  # noqa: BLE001 — belt and suspenders
                        logger.exception("swarm worker leaked for %s", lead.lead_id)
                        report.failed += 1
                        report.processed += 1
                        self.tracer.event(
                            "swarm.worker_crash",
                            {"lead_id": lead.lead_id, "error": str(exc)},
                        )
                        continue
                    report.processed += 1
                    report.results.append(result)
                    if result.ok:
                        report.succeeded += 1
                    else:
                        report.failed += 1
                    if result.research.degraded:
                        report.degraded += 1

        report.weights_after = self.store.get_weights()
        report.top_patterns = [p.pattern_id for p in self.store.list_patterns()[:5]]
        if hasattr(self.queue, "persist"):
            try:
                self.queue.persist()
            except Exception as exc:  # noqa: BLE001
                logger.warning("queue persist failed: %s", exc)
        return report

    def run_loop(self, interval: int, *, max_batches: Optional[int] = None) -> list[SwarmReport]:
        reports: list[SwarmReport] = []
        batch = 0
        while True:
            reports.append(self.run_once())
            batch += 1
            if max_batches is not None and batch >= max_batches:
                break
            time.sleep(interval)
        return reports

    def _safe_run(self, lead, swarm_id: str, index: int) -> PipelineResult:
        worker_id = f"worker-{index % self.concurrency}"
        pipeline: OutreachPipeline = self.pipeline_factory()
        try:
            return pipeline.run(lead, swarm_id=swarm_id, worker_id=worker_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("worker %s failed on %s", worker_id, lead.lead_id)
            self.tracer.event(
                "swarm.worker_isolated_failure",
                {"worker_id": worker_id, "lead_id": lead.lead_id, "error": str(exc)},
            )
            from self_improving_outreach.models import AgentRun, ResearchBundle, ScoreResult

            return PipelineResult(
                run=AgentRun(
                    swarm_id=swarm_id,
                    lead_id=lead.lead_id,
                    worker_id=worker_id,
                    status="failed",
                    error=str(exc),
                ),
                lead=lead,
                research=ResearchBundle(query="", degraded=True, source="worker_crash"),
                score=ScoreResult(total=0, features={}, weights={}),
                error=str(exc),
            )
