"""Deterministic Researcher / Scorer / Drafter / Critic / Learner crew."""

from __future__ import annotations

import logging
from typing import Optional

from self_improving_outreach import brand
from self_improving_outreach.config import Settings
from self_improving_outreach.human_gate import apply_human_gate
from self_improving_outreach.learning.learner import apply_learn_event, simulate_outcome
from self_improving_outreach.learning.scorer import score_lead
from self_improving_outreach.models import (
    AgentRun,
    Channel,
    Critique,
    Draft,
    Lead,
    LeadStatus,
    LearnEvent,
    Outcome,
    OutreachEvent,
    PipelineResult,
    ResearchBundle,
    ScoreResult,
    new_id,
    utcnow,
)
from self_improving_outreach.observability.tracing import LoggingTracer, RunTracer
from self_improving_outreach.stores.base import OutreachStore
from self_improving_outreach.tools.you_com import ResilientYouCom

logger = logging.getLogger(__name__)


def pick_pattern(store: OutreachStore, channel: Channel) -> tuple[str, str, str]:
    patterns = [p for p in store.list_patterns() if p.channel == channel] or store.list_patterns()
    if not patterns:
        return "cfo-cio-copilot", brand.DEFAULT_ANGLES[-1], "{body}"
    best = patterns[0]
    return best.pattern_id, best.angle, best.template


def draft_message(lead: Lead, store: OutreachStore, channel: Channel) -> Draft:
    pattern_id, angle, template = pick_pattern(store, channel)
    body = template.format(
        contact_name=lead.contact_name or "there",
        company=lead.company,
        founder=brand.FOUNDER,
        brand=brand.BRAND,
        industry=lead.industry or "finance",
    )
    subject = f"{brand.BRAND} × {lead.company}: {angle}"
    return Draft(channel=channel, pattern_id=pattern_id, angle=angle, subject=subject, body=body)


def critique_draft(draft: Draft) -> Critique:
    issues: list[str] = []
    body = draft.body
    if brand.has_brand_misspelling(body):
        issues.append("brand misspelling")
        body = brand.rewrite_brand_spelling(body)
    if brand.BRAND not in body:
        issues.append("missing Cubiczan brand")
        body = f"{body}\n\n— {brand.FOUNDER}, {brand.BRAND}"
    if any(word in body.lower() for word in ("guarantee", "guaranteed", "risk-free")):
        issues.append("overclaim")
        body = body.replace("guarantee", "aim").replace("guaranteed", "designed")
    if len(body) > 1400:
        issues.append("too long")
        body = body[:1400].rsplit(" ", 1)[0] + "…"
    return Critique(accepted=len(issues) == 0, issues=issues, revised_body=body)


class OutreachPipeline:
    """Closed-loop unit: research → score → draft → critic → gate → log → learn."""

    def __init__(
        self,
        settings: Settings,
        store: OutreachStore,
        you: ResilientYouCom,
        tracer: RunTracer,
        channel: Optional[Channel] = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.you = you
        self.tracer = tracer
        self.channel = channel or Channel(settings.default_channel)

    def run(
        self,
        lead: Lead,
        *,
        swarm_id: Optional[str] = None,
        worker_id: str = "",
        outcome: Optional[Outcome] = None,
    ) -> PipelineResult:
        self.store.upsert_lead(lead)
        run = AgentRun(
            run_id=new_id(),
            swarm_id=swarm_id,
            lead_id=lead.lead_id,
            worker_id=worker_id,
            status="started",
        )
        tracer = self.tracer
        if isinstance(tracer, LoggingTracer):
            tracer.run_id = run.run_id
        try:
            self.store.set_lead_status(lead.lead_id, LeadStatus.PROCESSING)
            with tracer.span("crew.run", {"lead_id": lead.lead_id, "company": lead.company}):
                with tracer.span("researcher"):
                    research = self.you.refresh(lead, run.run_id)
                with tracer.span("scorer"):
                    score = score_lead(lead, self.store, research)
                with tracer.span("drafter"):
                    draft = self._maybe_crewai_draft(lead, research, score)
                    if draft is None:
                        draft = draft_message(lead, self.store, self.channel)
                with tracer.span("critic"):
                    critique = critique_draft(draft)
                    if critique.revised_body:
                        draft.body = critique.revised_body
                        draft.critic_notes = critique.issues
                with tracer.span("human_gate"):
                    gate = apply_human_gate(lead, draft, self.settings)
                event = OutreachEvent(
                    lead_id=lead.lead_id,
                    run_id=run.run_id,
                    channel=draft.channel,
                    outcome=Outcome.DRAFTED,
                    angle=draft.angle,
                    pattern_id=draft.pattern_id,
                    body=draft.body,
                    metadata={
                        "score": score.total,
                        "degraded": research.degraded,
                        "gate": gate.status.value,
                    },
                )
                self.store.log_event(event)
                self.store.set_lead_status(lead.lead_id, gate.status)

                learned = False
                resolved_outcome = outcome
                if resolved_outcome is None and self.settings.simulate_outcomes and self.settings.is_mock:
                    resolved_outcome = simulate_outcome(score.total, draft.angle)
                if resolved_outcome is not None and resolved_outcome != Outcome.DRAFTED:
                    learn_event = LearnEvent(
                        lead_id=lead.lead_id,
                        outcome=resolved_outcome,
                        run_id=run.run_id,
                        pattern_id=draft.pattern_id,
                        angle=draft.angle,
                        features=score.features,
                    )
                    with tracer.span("learner"):
                        apply_learn_event(self.store, learn_event, lead)
                    self.store.log_event(
                        OutreachEvent(
                            lead_id=lead.lead_id,
                            run_id=run.run_id,
                            channel=draft.channel,
                            outcome=resolved_outcome,
                            angle=draft.angle,
                            pattern_id=draft.pattern_id,
                            body=draft.body,
                            metadata={"simulated": outcome is None},
                        )
                    )
                    learned = True

                if self.settings.livekit_feedback_auto:
                    from self_improving_outreach.voice.livekit_agent import (
                        maybe_apply_auto_voice_feedback,
                    )

                    with tracer.span("voice.feedback"):
                        if maybe_apply_auto_voice_feedback(
                            self.settings,
                            self.store,
                            lead,
                            run_id=run.run_id,
                            pattern_id=draft.pattern_id,
                        ):
                            learned = True

            run.status = "succeeded"
            run.finished_at = utcnow()
            run.traces = tracer.records()
            self.store.log_run(run)
            lead = self.store.get_lead(lead.lead_id) or lead
            return PipelineResult(
                run=run,
                lead=lead,
                research=research,
                score=score,
                draft=draft,
                critique=critique,
                gate=gate,
                event=event,
                learned=learned,
            )
        except Exception as exc:  # noqa: BLE001 — worker isolation happens in the swarm
            logger.exception("pipeline failed for %s", lead.lead_id)
            run.status = "failed"
            run.error = str(exc)
            run.finished_at = utcnow()
            run.traces = tracer.records()
            self.store.log_run(run)
            self.store.set_lead_status(lead.lead_id, LeadStatus.FAILED)
            cached = ""
            try:
                cached = self.store.cached_context(lead)
            except Exception:
                cached = lead.cached_context
            return PipelineResult(
                run=run,
                lead=lead,
                research=ResearchBundle(query="", synthesis=cached, source="error", degraded=True),
                score=ScoreResult(total=0, features={}, weights={}),
                error=str(exc),
            )

    def _maybe_crewai_draft(self, lead, research, score):
        if not self.settings.use_crewai:
            return None
        try:
            from self_improving_outreach.crews.crewai_adapter import run_crewai_draft

            return run_crewai_draft(self.settings, lead, research, score, self.store, self.channel)
        except Exception as exc:  # noqa: BLE001
            logger.warning("CrewAI draft failed, using deterministic drafter: %s", exc)
            self.tracer.event("crewai.fallback", {"error": str(exc)})
            return None
