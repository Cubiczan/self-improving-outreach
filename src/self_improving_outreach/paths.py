"""Locate repo-root sample data whether running from source or a checkout."""

from pathlib import Path


def sample_queue_path() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / "data" / "leads.sample.json",
        here.parents[2] / "data" / "leads.sample.json",
        here.parents[1] / "data" / "leads.sample.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]
