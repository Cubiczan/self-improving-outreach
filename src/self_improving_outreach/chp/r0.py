"""R0 foundation commit: independent peer seals, then a composed envelope."""

from __future__ import annotations

from typing import Any

from self_improving_outreach.brand import has_brand_misspelling
from self_improving_outreach.chp.exceptions import ImmutableCommitError
from self_improving_outreach.chp.hashing import canonical_digest
from self_improving_outreach.chp.models import FoundationCommit, R0GateResult, SealedPeer
from self_improving_outreach.chp.optional import import_evaluate_r0_gate
from self_improving_outreach.models import Draft, Lead, ResearchBundle, ScoreResult


PEER_FIELDS = {
    "research": ("query", "synthesis", "source", "degraded"),
    "score": ("total", "features", "weights"),
    "draft": ("channel", "pattern_id", "angle", "subject", "body"),
}


def _peer_payload(name: str, raw: dict[str, Any]) -> dict[str, Any]:
    allowed = PEER_FIELDS[name]
    return {key: raw.get(key) for key in allowed}


def seal_peer(name: str, raw: dict[str, Any]) -> SealedPeer:
    if name not in PEER_FIELDS:
        raise ValueError(f"unknown CHP peer {name!r}")
    payload = _peer_payload(name, raw)
    return SealedPeer(name=name, digest=canonical_digest(payload), payload=payload)


def verify_peer(peer: SealedPeer) -> None:
    expected = canonical_digest(_peer_payload(peer.name, peer.payload))
    if expected != peer.digest:
        raise ImmutableCommitError(f"{peer.name} seal digest mismatch")


def evaluate_r0_gate(
    *,
    solvable: bool,
    scoped: bool,
    valid: bool,
    worth_it: bool,
) -> R0GateResult:
    imported = import_evaluate_r0_gate()
    if imported is not None:
        evaluation = imported(
            solvable=solvable, scoped=scoped, valid=valid, worth_it=worth_it
        )
        results = dict(getattr(evaluation, "results", {}))
        verdict = getattr(evaluation, "verdict", None)
        verdict_text = getattr(verdict, "value", verdict) or "PASS"
        return R0GateResult(results=results, verdict=str(verdict_text), source="cme.chp")
    results = {
        "Solvable": "PASS" if solvable else "FATAL",
        "Scoped": "PASS" if scoped else "FATAL",
        "Valid": "PASS" if valid else "FATAL",
        "Worth_it": "PASS" if worth_it else "FATAL",
    }
    verdict = "PASS" if all(value == "PASS" for value in results.values()) else "HALT"
    return R0GateResult(results=results, verdict=verdict, source="local")


def r0_gate_from_unit(
    lead: Lead,
    research: ResearchBundle,
    score: ScoreResult,
    draft: Draft,
) -> R0GateResult:
    solvable = bool(lead.company.strip() and draft.body.strip())
    scoped = bool(draft.channel and (draft.pattern_id or draft.angle))
    valid = bool(draft.body.strip()) and not has_brand_misspelling(draft.body)
    worth_it = score.total >= 0 and bool(score.features or score.weights or draft.body)
    return evaluate_r0_gate(solvable=solvable, scoped=scoped, valid=valid, worth_it=worth_it)


def compose_r0_digest(peers: dict[str, SealedPeer], gate: R0GateResult) -> str:
    envelope = {
        "draft": peers["draft"].digest,
        "gate": gate.model_dump(),
        "research": peers["research"].digest,
        "score": peers["score"].digest,
    }
    return canonical_digest(envelope)


def commit_r0(
    lead: Lead,
    research: ResearchBundle,
    score: ScoreResult,
    draft: Draft,
    *,
    run_id: str,
) -> FoundationCommit:
    """Seal each peer independently, then compose R0. Order: research, score, draft."""
    research_peer = seal_peer(
        "research",
        {
            "query": research.query,
            "synthesis": research.synthesis,
            "source": research.source,
            "degraded": research.degraded,
        },
    )
    score_peer = seal_peer(
        "score",
        {
            "total": score.total,
            "features": score.features,
            "weights": score.weights,
        },
    )
    draft_peer = seal_peer(
        "draft",
        {
            "channel": draft.channel.value,
            "pattern_id": draft.pattern_id,
            "angle": draft.angle,
            "subject": draft.subject,
            "body": draft.body,
        },
    )
    peers = {
        "research": research_peer,
        "score": score_peer,
        "draft": draft_peer,
    }
    for peer in peers.values():
        verify_peer(peer)
    gate = r0_gate_from_unit(lead, research, score, draft)
    return FoundationCommit(
        lead_id=lead.lead_id,
        run_id=run_id,
        peers=peers,
        gate=gate,
        digest=compose_r0_digest(peers, gate),
    )


def verify_r0(commit: FoundationCommit) -> None:
    if len(commit.peers) != 3 or set(commit.peers) != {"research", "score", "draft"}:
        raise ImmutableCommitError("R0 must include research, score, and draft seals")
    for peer in commit.peers.values():
        verify_peer(peer)
    expected = compose_r0_digest(commit.peers, commit.gate)
    if expected != commit.digest:
        raise ImmutableCommitError("R0 foundation digest mismatch")
