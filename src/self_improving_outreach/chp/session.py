"""CHP session: R0 → adversary → provisional → named lock → pack → scout."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from self_improving_outreach.chp.adversary import run_structural_adversary
from self_improving_outreach.chp.exceptions import (
    AdversaryRequiredError,
    EvidencePackError,
    NamedActorRequired,
    R0GateHalt,
)
from self_improving_outreach.chp.hashing import canonical_digest
from self_improving_outreach.chp.models import (
    ChpDecision,
    ChpPhase,
    EvidencePack,
    HumanLock,
)
from self_improving_outreach.chp.r0 import commit_r0, verify_r0
from self_improving_outreach.config import Settings
from self_improving_outreach.human_gate import apply_human_gate
from self_improving_outreach.models import (
    Critique,
    Draft,
    GateDecision,
    Lead,
    LeadStatus,
    ResearchBundle,
    ScoreResult,
)
from self_improving_outreach.stores.base import OutreachStore

RESERVED_ACTORS = frozenset({"system", "auto", "anonymous", "bot", "pipeline", "scout"})


def _normalize_actor(actor: str) -> str:
    name = (actor or "").strip()
    if not name or name.lower() in RESERVED_ACTORS:
        raise NamedActorRequired(
            "CHP lock requires a named human actor (not empty, system, auto, anonymous, or bot)"
        )
    return name


def start_chp_session(
    lead: Lead,
    research: ResearchBundle,
    score: ScoreResult,
    draft: Draft,
    *,
    run_id: str,
    skip_adversary: bool = False,
    crewai_notes: Optional[list[str]] = None,
) -> ChpDecision:
    r0 = commit_r0(lead, research, score, draft, run_id=run_id)
    decision = ChpDecision(
        lead_id=lead.lead_id,
        run_id=run_id,
        phase=ChpPhase.EXPLORING,
        r0=r0,
    )
    if skip_adversary:
        raise AdversaryRequiredError("structural adversary is not skippable when CHP lock is on")
    extras = list(crewai_notes or []) + list(getattr(draft, "adversary_notes", None) or [])
    decision.adversary = run_structural_adversary(
        r0, draft, research, skip=False, crewai_notes=extras
    )
    decision.phase = ChpPhase.ADVISORY
    decision.phase = ChpPhase.PROVISIONAL
    decision.touch()
    return decision


def seal_evidence_pack(decision: ChpDecision) -> EvidencePack:
    if decision.r0 is None or decision.adversary is None or decision.lock is None:
        raise EvidencePackError("evidence pack requires sealed R0, adversary, and lock")
    verify_r0(decision.r0)
    if decision.adversary.r0_digest != decision.r0.digest:
        raise EvidencePackError("adversary report is not bound to this R0")
    if not decision.adversary.digest:
        raise EvidencePackError("adversary report missing digest")
    if not decision.lock.digest:
        raise EvidencePackError("lock record missing digest")
    pack = EvidencePack(
        r0_digest=decision.r0.digest,
        adversary_digest=decision.adversary.digest,
        lock_digest=decision.lock.digest,
        pack_digest=canonical_digest(
            {
                "adversary": decision.adversary.digest,
                "lock": decision.lock.digest,
                "r0": decision.r0.digest,
            }
        ),
    )
    decision.evidence_pack = pack
    return pack


def verify_evidence_pack(decision: ChpDecision) -> EvidencePack:
    pack = decision.evidence_pack
    if pack is None:
        raise EvidencePackError("no evidence pack")
    if decision.r0 is None or decision.adversary is None or decision.lock is None:
        raise EvidencePackError("pack references missing R0, adversary, or lock")
    verify_r0(decision.r0)
    if decision.adversary.digest != canonical_digest(
        decision.adversary.model_dump(exclude={"digest"})
    ):
        raise EvidencePackError("adversary report mutated after seal")
    if decision.lock.digest != canonical_digest(decision.lock.model_dump(exclude={"digest"})):
        raise EvidencePackError("lock record mutated after seal")
    expected = canonical_digest(
        {
            "adversary": decision.adversary.digest,
            "lock": decision.lock.digest,
            "r0": decision.r0.digest,
        }
    )
    if (
        pack.pack_digest != expected
        or pack.r0_digest != decision.r0.digest
        or pack.adversary_digest != decision.adversary.digest
        or pack.lock_digest != decision.lock.digest
    ):
        raise EvidencePackError("evidence pack digest mismatch")
    return pack


def apply_named_lock(
    decision: ChpDecision,
    *,
    actor: str,
    approve: bool,
    notes: str = "",
) -> ChpDecision:
    name = _normalize_actor(actor)
    if decision.phase not in {ChpPhase.PROVISIONAL, ChpPhase.ADVISORY}:
        raise NamedActorRequired(f"lock is only valid from provisional, not {decision.phase.value}")
    if decision.r0 is None or decision.adversary is None:
        raise EvidencePackError("cannot lock without R0 and adversary")
    verify_r0(decision.r0)
    if approve and decision.r0.gate.verdict != "PASS":
        raise R0GateHalt("named approve refused: R0 foundation gate is HALT")
    if decision.adversary.skippable:
        raise AdversaryRequiredError("adversary report marked skippable")
    lock = HumanLock(
        actor=name,
        decision="approve" if approve else "deny",
        notes=notes,
    )
    lock.digest = canonical_digest(lock.model_dump(exclude={"digest"}))
    decision.lock = lock
    decision.touch()
    if not approve:
        decision.phase = ChpPhase.PROVISIONAL
        decision.evidence_pack = None
        return decision
    seal_evidence_pack(decision)
    decision.phase = ChpPhase.LOCKED
    decision.touch()
    return decision


def promote_to_scout(decision: ChpDecision) -> LeadStatus:
    if decision.phase != ChpPhase.LOCKED:
        raise EvidencePackError("approved_for_scout requires phase locked")
    verify_evidence_pack(decision)
    if decision.lock is None or decision.lock.decision != "approve":
        raise EvidencePackError("approved_for_scout requires a named approve lock")
    return LeadStatus.APPROVED_FOR_SCOUT


def apply_chp_pipeline_gate(
    lead: Lead,
    draft: Draft,
    settings: Settings,
    *,
    research: ResearchBundle,
    score: ScoreResult,
    run_id: str,
    critique: Optional[Critique] = None,
    store: Optional[OutreachStore] = None,
) -> tuple[GateDecision, ChpDecision]:
    extras = list(getattr(draft, "adversary_notes", None) or [])
    if critique is not None:
        extras.extend(critique.issues)
    decision = start_chp_session(
        lead,
        research,
        score,
        draft,
        run_id=run_id,
        crewai_notes=extras,
    )
    if store is not None:
        save_chp_decision(settings, store, decision)
    else:
        _write_jsonl(settings, decision)
    notes = (
        f"CHP {decision.phase.value}: awaiting named human lock. "
        "Pipeline Scout still owns send."
    )
    if settings.human_gate_enabled:
        apply_human_gate(lead, draft, settings)
    return (
        GateDecision(
            approved=False,
            status=LeadStatus.PROVISIONAL,
            notes=notes,
        ),
        decision,
    )


def save_chp_decision(settings: Settings, store: OutreachStore, decision: ChpDecision) -> None:
    store.save_chp_decision(decision)
    _write_jsonl(settings, decision)


def load_chp_decision(
    settings: Settings,
    store: OutreachStore,
    lead_id: str,
) -> Optional[ChpDecision]:
    stored = store.get_chp_decision(lead_id)
    if stored is not None:
        return stored
    return _read_jsonl(settings, lead_id)


def apply_lock_and_promote(
    settings: Settings,
    store: OutreachStore,
    lead_id: str,
    *,
    actor: str,
    approve: bool,
    notes: str = "",
) -> tuple[ChpDecision, LeadStatus]:
    decision = load_chp_decision(settings, store, lead_id)
    if decision is None:
        raise EvidencePackError(f"no CHP decision for lead {lead_id}")
    apply_named_lock(decision, actor=actor, approve=approve, notes=notes)
    status = LeadStatus.PROVISIONAL
    if approve:
        status = promote_to_scout(decision)
    store.set_lead_status(lead_id, status)
    save_chp_decision(settings, store, decision)
    return decision, status


def _jsonl_path(settings: Settings) -> Path:
    return Path(settings.chp_decisions_path)


def _write_jsonl(settings: Settings, decision: ChpDecision) -> None:
    path = _jsonl_path(settings)
    rows = _load_jsonl_rows(path)
    rows[decision.lead_id] = decision.model_dump(mode="json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for payload in rows.values():
            handle.write(json.dumps(payload, default=str) + "\n")


def _read_jsonl(settings: Settings, lead_id: str) -> Optional[ChpDecision]:
    rows = _load_jsonl_rows(_jsonl_path(settings))
    payload = rows.get(lead_id)
    if payload is None:
        return None
    return ChpDecision.model_validate(payload)


def _load_jsonl_rows(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        rows[payload["lead_id"]] = payload
    return rows
