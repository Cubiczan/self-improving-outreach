"""Pydantic models for the outreach CHP decision lock."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from self_improving_outreach.models import LeadStatus, new_id, utcnow


class ChpPhase(str, Enum):
    EXPLORING = "exploring"
    ADVISORY = "advisory"
    PROVISIONAL = "provisional"
    LOCKED = "locked"

    def as_lead_status(self) -> LeadStatus:
        return LeadStatus(self.value)


class SealedPeer(BaseModel):
    """One independently sealed peer. Payload contains only that peer's fields."""

    name: str
    digest: str
    payload: dict[str, Any] = Field(default_factory=dict)


class R0GateResult(BaseModel):
    results: dict[str, str] = Field(default_factory=dict)
    verdict: str = "PASS"
    source: str = "local"


class FoundationCommit(BaseModel):
    commit_id: str = Field(default_factory=new_id)
    lead_id: str
    run_id: str
    peers: dict[str, SealedPeer] = Field(default_factory=dict)
    gate: R0GateResult = Field(default_factory=R0GateResult)
    digest: str = ""
    sealed_at: str = Field(default_factory=lambda: utcnow().isoformat())


class AdversaryReport(BaseModel):
    r0_digest: str
    skippable: bool = False
    findings: list[str] = Field(default_factory=list)
    structural_vulnerabilities: list[str] = Field(default_factory=list)
    foundation_score: int = 100
    attack_summary: str = ""
    crewai_adversary_notes: list[str] = Field(default_factory=list)
    digest: str = ""


class HumanLock(BaseModel):
    actor: str
    decision: str
    notes: str = ""
    locked_at: str = Field(default_factory=lambda: utcnow().isoformat())
    digest: str = ""


class EvidencePack(BaseModel):
    model_config = ConfigDict(frozen=True)

    r0_digest: str
    adversary_digest: str
    lock_digest: str
    pack_digest: str
    sealed_at: str = Field(default_factory=lambda: utcnow().isoformat())


class ChpDecision(BaseModel):
    decision_id: str = Field(default_factory=new_id)
    lead_id: str
    run_id: str
    phase: ChpPhase = ChpPhase.EXPLORING
    r0: Optional[FoundationCommit] = None
    adversary: Optional[AdversaryReport] = None
    lock: Optional[HumanLock] = None
    evidence_pack: Optional[EvidencePack] = None
    created_at: str = Field(default_factory=lambda: utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: utcnow().isoformat())

    def touch(self) -> None:
        self.updated_at = utcnow().isoformat()
