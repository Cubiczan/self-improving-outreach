"""Shared pydantic models for leads, drafts, outcomes, and run reports."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class LeadStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DRAFTED = "drafted"
    PENDING_REVIEW = "pending_review"
    EXPLORING = "exploring"
    ADVISORY = "advisory"
    PROVISIONAL = "provisional"
    LOCKED = "locked"
    APPROVED_FOR_SCOUT = "approved_for_scout"
    FAILED = "failed"
    LEARNED = "learned"


class Channel(str, Enum):
    LINKEDIN = "linkedin"
    EMAIL = "email"
    VOICE = "voice"


class Outcome(str, Enum):
    DRAFTED = "drafted"
    SENT = "sent"
    REPLIED = "replied"
    MEETING = "meeting"
    IGNORE = "ignore"
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"


POSITIVE_OUTCOMES = {Outcome.REPLIED, Outcome.MEETING, Outcome.THUMBS_UP}
NEGATIVE_OUTCOMES = {Outcome.IGNORE, Outcome.THUMBS_DOWN}


class Lead(BaseModel):
    lead_id: str = Field(default_factory=new_id)
    company: str
    domain: str = ""
    contact_name: str = ""
    title: str = ""
    industry: str = ""
    location: str = ""
    signals: dict[str, Any] = Field(default_factory=dict)
    cached_context: str = ""
    status: LeadStatus = LeadStatus.QUEUED
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Snippet(BaseModel):
    title: str = ""
    url: str = ""
    text: str = ""


class ResearchBundle(BaseModel):
    query: str
    snippets: list[Snippet] = Field(default_factory=list)
    synthesis: str = ""
    source: str = "you.com"
    degraded: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)

    def as_text(self, limit: int = 4000) -> str:
        parts = [self.synthesis] if self.synthesis else []
        for snip in self.snippets:
            line = " ".join(p for p in (snip.title, snip.url, snip.text) if p)
            if line:
                parts.append(line)
        text = "\n".join(parts).strip()
        return text[:limit]


class ScoreResult(BaseModel):
    total: float
    features: dict[str, float]
    weights: dict[str, float]
    rationale: str = ""


class Draft(BaseModel):
    channel: Channel = Channel.LINKEDIN
    pattern_id: str
    angle: str
    subject: str = ""
    body: str
    critic_notes: list[str] = Field(default_factory=list)
    adversary_notes: list[str] = Field(default_factory=list)


class Critique(BaseModel):
    accepted: bool
    issues: list[str] = Field(default_factory=list)
    revised_body: Optional[str] = None


class GateDecision(BaseModel):
    approved: bool
    status: LeadStatus
    notes: str = ""


class OutreachEvent(BaseModel):
    event_id: str = Field(default_factory=new_id)
    lead_id: str
    run_id: str
    channel: Channel = Channel.LINKEDIN
    outcome: Outcome = Outcome.DRAFTED
    angle: str = ""
    pattern_id: str = ""
    body: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class MessagePattern(BaseModel):
    pattern_id: str
    angle: str
    channel: Channel = Channel.LINKEDIN
    template: str
    wins: int = 0
    losses: int = 0
    impressions: int = 0
    score: float = 0.5
    updated_at: datetime = Field(default_factory=utcnow)


class IcpWeight(BaseModel):
    feature: str
    weight: float
    version: int = 1
    updated_at: datetime = Field(default_factory=utcnow)


class ToolFailure(BaseModel):
    failure_id: str = Field(default_factory=new_id)
    run_id: str
    tool_name: str
    error_class: str
    message: str
    retry_attempt: int = 1
    degraded: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class AgentRun(BaseModel):
    run_id: str = Field(default_factory=new_id)
    swarm_id: Optional[str] = None
    lead_id: str
    status: str = "started"
    traces: list[dict[str, Any]] = Field(default_factory=list)
    worker_id: str = ""
    error: Optional[str] = None
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: Optional[datetime] = None


class PipelineResult(BaseModel):
    run: AgentRun
    lead: Lead
    research: ResearchBundle
    score: ScoreResult
    draft: Optional[Draft] = None
    critique: Optional[Critique] = None
    gate: Optional[GateDecision] = None
    chp: Optional[Any] = None
    event: Optional[OutreachEvent] = None
    learned: bool = False
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.draft is not None


class LearnEvent(BaseModel):
    lead_id: str
    outcome: Outcome
    run_id: Optional[str] = None
    pattern_id: Optional[str] = None
    angle: Optional[str] = None
    features: dict[str, float] = Field(default_factory=dict)
    notes: str = ""


class SwarmReport(BaseModel):
    swarm_id: str
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    degraded: int = 0
    results: list[PipelineResult] = Field(default_factory=list)
    weights_after: dict[str, float] = Field(default_factory=dict)
    top_patterns: list[str] = Field(default_factory=list)
