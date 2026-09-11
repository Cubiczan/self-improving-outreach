"""Soft-import Cubiczan ``cme.chp`` — missing package is not an error."""

from __future__ import annotations

from typing import Any, Optional


def import_evaluate_r0_gate() -> Optional[Any]:
    try:
        from cme.chp.gates import evaluate_r0_gate

        return evaluate_r0_gate
    except Exception:
        pass
    try:
        from consensus_hardening_protocol.gates import evaluate_r0_gate  # type: ignore

        return evaluate_r0_gate
    except Exception:
        return None
