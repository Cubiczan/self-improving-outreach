"""Canonical SHA-256 digests for sealed CHP payloads."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def canonical_digest(payload: Any) -> str:
    return hashlib.sha256(canonical_dumps(payload).encode("utf-8")).hexdigest()
