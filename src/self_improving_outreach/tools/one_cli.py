"""One (withone.ai) CLI adapter.

Invokes ``one --agent`` so ``ONE_SECRET`` and existing CLI auth both work.
Never logs secrets or connection keys. Tests should mock ``subprocess.run``.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Optional

from self_improving_outreach.one_defaults import (
    DEFAULT_DAYTONA_CREATE_SANDBOX_ACTION_ID,
    DEFAULT_YOU_RESEARCH_ACTION_ID,
    DEFAULT_YOU_SEARCH_ACTION_ID,
)

# Action definition IDs are public (not credentials). Override via env.
YOU_PLATFORM = "you"
DAYTONA_PLATFORM = "daytona"


class OneError(Exception):
    """Raised when the One CLI is missing, unauthenticated, or an action fails."""


def _parse_json_stdout(stdout: str) -> Any:
    text = (stdout or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise OneError("One CLI returned non-JSON output") from None


def unwrap_one_response(payload: Any) -> Any:
    """Peel One agent envelopes down to the platform API body."""
    if not isinstance(payload, dict):
        return payload
    current: Any = payload
    for _ in range(4):
        if not isinstance(current, dict):
            return current
        nested = None
        for key in ("response", "data", "result", "body", "output"):
            if key in current and isinstance(current[key], (dict, list)):
                nested = current[key]
                break
        if nested is None:
            return current
        current = nested
    return current


def extract_action_id(payload: Any) -> Optional[str]:
    """Best-effort first action id from ``one --agent actions search`` JSON."""
    if isinstance(payload, dict):
        for key in ("actionId", "action_id"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        for key in ("actions", "results", "data", "items"):
            if key in payload:
                found = extract_action_id(payload[key])
                if found:
                    return found
    elif isinstance(payload, list):
        for item in payload:
            found = extract_action_id(item)
            if found:
                return found
    return None


def _config_has_secret(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if path.name == ".onerc":
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            if key.strip() == "ONE_SECRET" and value.strip():
                return True
        return False
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict):
        return False
    for key in ("apiKey", "oneSecret", "secret", "ONE_SECRET"):
        if data.get(key):
            return True
    return False


def local_one_config_present() -> bool:
    """True when a local One CLI config looks authenticated (no secret values returned)."""
    if _config_has_secret(Path.cwd() / ".onerc"):
        return True
    home = Path.home() / ".one"
    if _config_has_secret(home / "config.json"):
        return True
    projects = home / "projects"
    if projects.is_dir():
        for child in projects.iterdir():
            if _config_has_secret(child / "config.json"):
                return True
    return False


class OneCli:
    """Thin ``one --agent`` subprocess runner."""

    def __init__(
        self,
        binary: str = "one",
        timeout: float = 90.0,
        extra_env: Optional[dict[str, str]] = None,
        runner=None,
    ) -> None:
        self.binary = binary
        self.timeout = timeout
        self.extra_env = extra_env or {}
        self._runner = runner or subprocess.run

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update(self.extra_env)
        return env

    def run(self, args: list[str], *, timeout: Optional[float] = None) -> Any:
        cmd = [self.binary, "--agent", *args]
        try:
            completed = self._runner(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
                env=self._env(),
                check=False,
            )
        except FileNotFoundError as exc:
            raise OneError(f"One CLI not found ({self.binary})") from exc
        except subprocess.TimeoutExpired as exc:
            raise OneError(f"One CLI timed out: {' '.join(args[:4])}") from exc
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if completed.returncode != 0:
            detail = (stderr or stdout).strip().splitlines()
            hint = detail[-1] if detail else f"exit {completed.returncode}"
            raise OneError(f"One CLI failed ({args[0:3]}): {hint}")
        return _parse_json_stdout(stdout)

    def whoami(self) -> Any:
        return self.run(["whoami"], timeout=min(self.timeout, 8.0))

    def search_actions(self, platform: str, query: str, *, type: str = "execute") -> Any:
        return self.run(["actions", "search", platform, query, "-t", type])

    def knowledge(self, platform: str, action_id: str) -> Any:
        return self.run(["actions", "knowledge", platform, action_id])

    def execute(
        self,
        platform: str,
        action_id: str,
        connection_key: str,
        *,
        data: Any = None,
        path_vars: Optional[dict[str, Any]] = None,
        query_params: Optional[dict[str, Any]] = None,
        skip_validation: bool = False,
        timeout: Optional[float] = None,
    ) -> Any:
        args = ["actions", "execute", platform, action_id, connection_key]
        if data is not None:
            args.extend(["-d", json.dumps(data)])
        if path_vars:
            args.extend(["--path-vars", json.dumps(path_vars)])
        if query_params:
            args.extend(["--query-params", json.dumps(query_params)])
        if skip_validation:
            args.append("--skip-validation")
        return self.run(args, timeout=timeout)

    def resolve_action_id(self, platform: str, query: str, configured: Optional[str] = None) -> str:
        if configured:
            return configured
        payload = self.search_actions(platform, query, type="execute")
        action_id = extract_action_id(payload)
        if not action_id:
            raise OneError(f"no One action for {platform!r} query {query!r}")
        return action_id
