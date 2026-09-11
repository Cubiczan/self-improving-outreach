"""Parse LiveKit / AE preference-interview transcripts for the Learner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

POSITIVE_TOKENS = {
    "positive",
    "pos",
    "thumbs_up",
    "thumbs-up",
    "thumbsup",
    "up",
    "yes",
    "true",
    "good",
    "like",
    "liked",
    "win",
}
NEGATIVE_TOKENS = {
    "negative",
    "neg",
    "thumbs_down",
    "thumbs-down",
    "thumbsdown",
    "down",
    "no",
    "false",
    "bad",
    "dislike",
    "disliked",
    "lose",
}


class VoiceTranscriptFeedback(BaseModel):
    positive: bool
    notes: str = ""
    pattern_id: Optional[str] = None
    lead_id: Optional[str] = None
    raw: dict[str, Any] = Field(default_factory=dict)


def _normalize_token(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _as_bool_sentiment(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, str):
        token = _normalize_token(value)
        if token in POSITIVE_TOKENS:
            return True
        if token in NEGATIVE_TOKENS:
            return False
    return None


def _first_present(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def parse_voice_transcript(payload: dict[str, Any]) -> VoiceTranscriptFeedback:
    """Extract positive/negative, notes, and pattern_id from a transcript JSON object."""
    if not isinstance(payload, dict):
        raise ValueError("Voice transcript must be a JSON object")

    nested = payload.get("feedback")
    layer = dict(payload)
    if isinstance(nested, dict):
        layer = {**payload, **nested}

    sentiment = None
    for key in ("positive", "sentiment", "outcome", "thumbs", "label", "polarity", "feedback"):
        value = layer.get(key)
        if isinstance(value, dict):
            continue
        sentiment = _as_bool_sentiment(value)
        if sentiment is not None:
            break
    if sentiment is None:
        raise ValueError(
            "Voice transcript must include positive/negative via "
            "'positive', 'sentiment', 'outcome', or 'thumbs'"
        )

    notes = _first_present(layer, ("notes", "note", "summary", "comment"))
    transcript_text = _first_present(layer, ("transcript", "text", "utterance"))
    notes_text = str(notes).strip() if notes is not None else ""
    if transcript_text:
        excerpt = str(transcript_text).strip()[:2000]
        if excerpt and excerpt not in notes_text:
            notes_text = f"{notes_text}\n{excerpt}".strip() if notes_text else excerpt

    pattern = _first_present(layer, ("pattern_id", "pattern", "angle_id"))
    lead_id = _first_present(layer, ("lead_id", "leadId", "id"))
    if lead_id is not None:
        lead_id = str(lead_id)

    return VoiceTranscriptFeedback(
        positive=sentiment,
        notes=notes_text,
        pattern_id=str(pattern) if pattern is not None else None,
        lead_id=lead_id,
        raw=payload,
    )


def parse_voice_transcript_file(path: Path | str) -> VoiceTranscriptFeedback:
    file_path = Path(path)
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid voice transcript JSON: {file_path}") from exc
    if isinstance(payload, list):
        if not payload:
            raise ValueError("Voice transcript list is empty")
        payload = payload[0]
    if not isinstance(payload, dict):
        raise ValueError("Voice transcript must be a JSON object")
    return parse_voice_transcript(payload)


def resolve_transcript_path(
    configured: Optional[str],
    lead_id: str,
    *,
    override: Optional[Path | str] = None,
) -> Optional[Path]:
    raw = override if override is not None else configured
    if not raw:
        return None
    path = Path(raw)
    if path.is_dir():
        for name in (f"{lead_id}.json", f"{lead_id}.transcript.json", "transcript.json"):
            candidate = path / name
            if candidate.is_file():
                return candidate
        return None
    if path.is_file():
        return path
    return None
