"""Cubiczan CHP decision lock for Self Improving Outreach.

Sealed R0, non-skippable structural adversary, named human lock, immutable
evidence pack. Soft-imports ``cme.chp`` when present; no hard dependency.
"""

from self_improving_outreach.chp.adversary import run_structural_adversary
from self_improving_outreach.chp.exceptions import (
    AdversaryRequiredError,
    ChpError,
    EvidencePackError,
    ImmutableCommitError,
    NamedActorRequired,
    R0GateHalt,
)
from self_improving_outreach.chp.models import (
    AdversaryReport,
    ChpDecision,
    ChpPhase,
    EvidencePack,
    FoundationCommit,
    HumanLock,
    SealedPeer,
)
from self_improving_outreach.chp.session import (
    apply_chp_pipeline_gate,
    apply_named_lock,
    load_chp_decision,
    promote_to_scout,
    save_chp_decision,
    start_chp_session,
    verify_evidence_pack,
)

__all__ = [
    "AdversaryReport",
    "AdversaryRequiredError",
    "ChpDecision",
    "ChpError",
    "ChpPhase",
    "EvidencePack",
    "EvidencePackError",
    "FoundationCommit",
    "HumanLock",
    "ImmutableCommitError",
    "NamedActorRequired",
    "R0GateHalt",
    "SealedPeer",
    "apply_chp_pipeline_gate",
    "apply_named_lock",
    "load_chp_decision",
    "promote_to_scout",
    "run_structural_adversary",
    "save_chp_decision",
    "start_chp_session",
    "verify_evidence_pack",
]
