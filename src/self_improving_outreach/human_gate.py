"""Human-gate stub. Send remains owned by Marketing Hunter / Pipeline Scout."""

from __future__ import annotations

import json
from pathlib import Path

from self_improving_outreach.config import Settings
from self_improving_outreach.models import Draft, GateDecision, Lead, LeadStatus, utcnow


def apply_human_gate(lead: Lead, draft: Draft, settings: Settings) -> GateDecision:
    if settings.human_gate_enabled:
        _append_pending(settings.pending_approvals_path, lead, draft)
        return GateDecision(
            approved=False,
            status=LeadStatus.PENDING_REVIEW,
            notes="Held for human / Pipeline Scout review",
        )
    return GateDecision(
        approved=True,
        status=LeadStatus.APPROVED_FOR_SCOUT,
        notes="Draft ready. Marketing Hunter / Pipeline Scout own LinkedIn send.",
    )


def _append_pending(path: str, lead: Lead, draft: Draft) -> None:
    payload = {
        "at": utcnow().isoformat(),
        "lead_id": lead.lead_id,
        "company": lead.company,
        "channel": draft.channel.value,
        "angle": draft.angle,
        "body": draft.body,
    }
    file_path = Path(path)
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
