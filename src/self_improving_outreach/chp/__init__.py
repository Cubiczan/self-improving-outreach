"""Cubiczan CHP decision lock for Self Improving Outreach.

Sealed R0, non-skippable structural adversary, named human lock, immutable
evidence pack. Soft-imports ``cme.chp`` when present; no hard dependency.

Session helpers are lazy: ``stores.base`` imports ``chp.models``, and loading
this package must not immediately import ``chp.session`` (which needs
``OutreachStore``).
"""

from importlib import import_module
from typing import Any

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

_SESSION_EXPORTS = frozenset(
    {
        "apply_chp_pipeline_gate",
        "apply_named_lock",
        "load_chp_decision",
        "promote_to_scout",
        "save_chp_decision",
        "start_chp_session",
        "verify_evidence_pack",
    }
)


def __getattr__(name: str) -> Any:
    if name not in _SESSION_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module("self_improving_outreach.chp.session"), name)
    globals()[name] = value
    return value
