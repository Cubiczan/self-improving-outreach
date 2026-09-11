"""Inbound integrations for the search + outreach queue (no paid ads)."""

from self_improving_outreach.integrations.clickup import (
    ClickUpIngestResult,
    ingest_clickup_payload,
    lead_from_clickup,
    unwrap_clickup_payload,
)

__all__ = [
    "ClickUpIngestResult",
    "ingest_clickup_payload",
    "lead_from_clickup",
    "unwrap_clickup_payload",
]
