"""Daytona sandbox lifecycle via One ``daytona`` actions."""

from __future__ import annotations

from typing import Any, Optional

from self_improving_outreach.tools.one_cli import (
    DAYTONA_PLATFORM,
    DEFAULT_DAYTONA_CREATE_SANDBOX_ACTION_ID,
    OneCli,
    OneError,
    unwrap_one_response,
)


class OneSandbox:
    """Minimal sandbox handle with the ``.delete()`` the tracer already calls."""

    def __init__(
        self,
        sandbox_id: str,
        *,
        client: "OneDaytonaClient",
        raw: Optional[dict[str, Any]] = None,
    ) -> None:
        self.id = sandbox_id
        self.client = client
        self.raw = raw or {}

    def delete(self) -> None:
        self.client.delete(self.id)


class OneDaytonaClient:
    """Create / start / list / delete sandboxes through One."""

    def __init__(
        self,
        connection_key: str,
        *,
        runner: Optional[OneCli] = None,
        create_action_id: str = DEFAULT_DAYTONA_CREATE_SANDBOX_ACTION_ID,
        start_action_id: Optional[str] = None,
        list_action_id: Optional[str] = None,
        delete_action_id: Optional[str] = None,
        sandbox_path_var: str = "sandboxIdOrName",
        timeout: float = 90.0,
    ) -> None:
        if not connection_key:
            raise OneError("ONE_DAYTONA_CONNECTION_KEY is required for One sandboxes")
        self.connection_key = connection_key
        self.runner = runner or OneCli(timeout=timeout)
        self.create_action_id = create_action_id
        self.start_action_id = start_action_id
        self.list_action_id = list_action_id
        self.delete_action_id = delete_action_id
        self.sandbox_path_var = sandbox_path_var

    def _execute(
        self,
        action_id: str,
        *,
        data: Any = None,
        path_vars: Optional[dict[str, Any]] = None,
        skip_validation: bool = False,
    ) -> Any:
        payload = self.runner.execute(
            DAYTONA_PLATFORM,
            action_id,
            self.connection_key,
            data=data,
            path_vars=path_vars,
            skip_validation=skip_validation,
        )
        return unwrap_one_response(payload)

    def _action(self, configured: Optional[str], query: str) -> str:
        return self.runner.resolve_action_id(DAYTONA_PLATFORM, query, configured)

    def create(self, data: Optional[dict[str, Any]] = None) -> OneSandbox:
        body = data if data is not None else {}
        payload = self._execute(
            self.create_action_id,
            data=body,
            skip_validation=not body,
        )
        sandbox_id = _sandbox_id(payload)
        if not sandbox_id:
            raise OneError("One Daytona create returned no sandbox id")
        sandbox = OneSandbox(sandbox_id, client=self, raw=payload if isinstance(payload, dict) else {})
        state = ""
        if isinstance(payload, dict):
            state = str(payload.get("state") or payload.get("desiredState") or "").lower()
        if state and state not in {"started", "running", "ready", "started_locally"}:
            try:
                self.start(sandbox_id)
            except OneError:
                # Create often starts the box; start is best-effort.
                pass
        return sandbox

    def start(self, sandbox_id: str) -> Any:
        action_id = self._action(self.start_action_id, "start resume sandbox")
        return self._execute(
            action_id,
            path_vars={self.sandbox_path_var: sandbox_id},
            skip_validation=True,
        )

    def list(self) -> Any:
        action_id = self._action(self.list_action_id, "list sandboxes")
        return self._execute(action_id, skip_validation=True)

    def delete(self, sandbox_id: str) -> Any:
        action_id = self._action(self.delete_action_id, "delete sandbox")
        return self._execute(
            action_id,
            path_vars={self.sandbox_path_var: sandbox_id},
            skip_validation=True,
        )


def _sandbox_id(payload: Any) -> Optional[str]:
    if isinstance(payload, str) and payload:
        return payload
    if not isinstance(payload, dict):
        return None
    for key in ("id", "sandboxId", "sandbox_id", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    nested = payload.get("sandbox")
    if isinstance(nested, dict):
        return _sandbox_id(nested)
    return None


def one_daytona_from_settings(settings: Any, *, runner: Optional[OneCli] = None) -> OneDaytonaClient:
    return OneDaytonaClient(
        settings.one_daytona_connection_key or "",
        runner=runner or OneCli(binary=settings.one_cli, timeout=settings.one_timeout_seconds),
        create_action_id=settings.one_daytona_create_sandbox_action_id,
        start_action_id=settings.one_daytona_start_sandbox_action_id,
        list_action_id=settings.one_daytona_list_sandbox_action_id,
        delete_action_id=settings.one_daytona_delete_sandbox_action_id,
        sandbox_path_var=settings.one_daytona_sandbox_path_var,
        timeout=settings.one_timeout_seconds,
    )
