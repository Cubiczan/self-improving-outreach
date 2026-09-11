"""Non-skippable structural adversary. CrewAI notes are extras only."""

from __future__ import annotations

from typing import Iterable, Optional

from self_improving_outreach import brand
from self_improving_outreach.chp.exceptions import AdversaryRequiredError, ImmutableCommitError
from self_improving_outreach.chp.hashing import canonical_digest
from self_improving_outreach.chp.models import AdversaryReport, FoundationCommit
from self_improving_outreach.chp.r0 import verify_r0
from self_improving_outreach.models import Draft, ResearchBundle


_SEND_PHRASES = (
    "i sent",
    "we sent",
    "already sent",
    "already messaged",
    "posted to linkedin",
    "emailed you already",
    "just sent this on linkedin",
)


def run_structural_adversary(
    r0: FoundationCommit,
    draft: Draft,
    research: ResearchBundle,
    *,
    skip: bool = False,
    crewai_notes: Optional[Iterable[str]] = None,
) -> AdversaryReport:
    if skip:
        raise AdversaryRequiredError("structural adversary is not skippable when CHP lock is on")
    verify_r0(r0)
    draft_peer = r0.peers["draft"]
    if draft.body != draft_peer.payload.get("body"):
        raise ImmutableCommitError("adversary saw a draft body that is not the sealed R0")

    findings: list[str] = []
    vulns: list[str] = []
    body = draft.body
    lower = body.lower()

    if brand.has_brand_misspelling(body):
        findings.append("brand misspelling")
        vulns.append("CubicZan or spaced Cubic Zan in sealed draft")
    if brand.BRAND not in body:
        findings.append("missing Cubiczan brand")
        vulns.append("sealed draft does not name Cubiczan")
    if any(word in lower for word in ("guarantee", "guaranteed", "risk-free")):
        findings.append("overclaim")
        vulns.append("overclaim language in sealed draft")
    if any(phrase in lower for phrase in _SEND_PHRASES):
        findings.append("send implication")
        vulns.append("draft implies LinkedIn or email already sent")
    if not body.strip():
        findings.append("empty body")
        vulns.append("sealed draft body is empty")
    if len(body) > 1400:
        findings.append("too long")
        vulns.append("sealed draft exceeds critic length budget")
    if research.degraded and "degraded" not in lower and "cached" not in lower:
        findings.append("undeclared research degrade")
        vulns.append("research degraded without disclosure in the draft")

    extras = [note for note in (crewai_notes or []) if note]
    score = max(0, 100 - 15 * len(findings))
    summary = (
        "structural adversary found no blocking issues"
        if not findings
        else "structural adversary: " + "; ".join(findings)
    )
    report = AdversaryReport(
        r0_digest=r0.digest,
        skippable=False,
        findings=findings,
        structural_vulnerabilities=vulns[:3],
        foundation_score=score,
        attack_summary=summary,
        crewai_adversary_notes=extras,
    )
    report.digest = canonical_digest(report.model_dump(exclude={"digest"}))
    return report
