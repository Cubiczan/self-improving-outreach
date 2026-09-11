"""Locate repo-root sample data whether running from source or a checkout."""

from pathlib import Path


def _first_existing(name: str) -> Path:
    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / "data" / name,
        here.parents[2] / "data" / name,
        here.parents[1] / "data" / name,
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def sample_queue_path() -> Path:
    return _first_existing("leads.sample.json")


def sample_voice_transcript_path() -> Path:
    return _first_existing("voice_transcript.sample.json")
