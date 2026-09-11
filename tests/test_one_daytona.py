import json
import os
import subprocess
import sys
import types
from pathlib import Path
from subprocess import CompletedProcess

from self_improving_outreach.config import Settings
from self_improving_outreach.observability.tracing import DaytonaTracer, LoggingTracer, build_tracer
from self_improving_outreach.one_defaults import DEFAULT_DAYTONA_DOCKERFILE, DEFAULT_DAYTONA_SNAPSHOT
from self_improving_outreach.tools.one_cli import OneCli
from self_improving_outreach.tools.one_daytona import (
    OneDaytonaClient,
    merge_sandbox_create_body,
    one_daytona_from_settings,
)


def _ok(cmd, payload):
    return CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")


def _execute_data(cmd):
    return json.loads(cmd[cmd.index("-d") + 1])


def test_merge_sandbox_create_body_fills_buildinfo_and_snapshot():
    body = merge_sandbox_create_body({"name": "cubiczan-outreach", "labels": {"app": "swarm"}})
    assert body["name"] == "cubiczan-outreach"
    assert body["labels"] == {"app": "swarm"}
    assert body["buildInfo"]["dockerfileContent"] == DEFAULT_DAYTONA_DOCKERFILE
    assert body["snapshot"] == DEFAULT_DAYTONA_SNAPSHOT


def test_merge_sandbox_create_body_caller_wins_and_blank_snapshot_omits():
    body = merge_sandbox_create_body(
        {
            "name": "custom",
            "snapshot": "my-snapshot",
            "buildInfo": {"dockerfileContent": "FROM ubuntu:22.04", "contextHashes": ["h1"]},
        }
    )
    assert body["snapshot"] == "my-snapshot"
    assert body["buildInfo"]["dockerfileContent"] == "FROM ubuntu:22.04"
    assert body["buildInfo"]["contextHashes"] == ["h1"]

    omitted = merge_sandbox_create_body({"name": "n"}, snapshot="")
    assert "snapshot" not in omitted
    assert omitted["buildInfo"]["dockerfileContent"] == DEFAULT_DAYTONA_DOCKERFILE

    env_override = merge_sandbox_create_body(
        {"name": "n"},
        dockerfile="FROM ubuntu:22.04",
        snapshot="daytonaio/sandbox:latest",
    )
    assert env_override["buildInfo"]["dockerfileContent"] == "FROM ubuntu:22.04"
    assert env_override["snapshot"] == "daytonaio/sandbox:latest"


def test_create_start_list_delete_via_one():
    calls = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        if cmd[2:4] == ["actions", "search"]:
            query = cmd[5]
            action = {
                "start": "act-start",
                "list": "act-list",
                "delete": "act-delete",
            }
            key = "start" if "start" in query else "list" if "list" in query else "delete"
            return _ok(cmd, {"actions": [{"actionId": action[key]}]})
        if cmd[5] == "conn_mod_def::GMgWX_S6VPA::VxlhHfBWQ4qfa9mXEX2OQQ":
            return _ok(cmd, {"response": {"id": "sbx-99", "state": "started"}})
        return _ok(cmd, {"ok": True})

    client = OneDaytonaClient(
        "live::daytona::default::test",
        runner=OneCli(runner=runner),
    )
    sandbox = client.create({"name": "cubiczan-outreach"})
    assert sandbox.id == "sbx-99"
    listed = client.list()
    assert listed == {"ok": True}
    sandbox.delete()
    execute_cmds = [c for c in calls if c[2:4] == ["actions", "execute"]]
    assert execute_cmds[0][4] == "daytona"
    create_cmd = execute_cmds[0]
    assert "-d" in create_cmd
    assert "--skip-validation" not in create_cmd
    created = _execute_data(create_cmd)
    assert created["name"] == "cubiczan-outreach"
    assert created["buildInfo"]["dockerfileContent"] == DEFAULT_DAYTONA_DOCKERFILE
    assert created["snapshot"] == DEFAULT_DAYTONA_SNAPSHOT
    assert "--path-vars" in execute_cmds[-1]
    assert json.loads(execute_cmds[-1][execute_cmds[-1].index("--path-vars") + 1]) == {
        "sandboxIdOrName": "sbx-99"
    }


def test_create_uses_client_dockerfile_and_snapshot_overrides():
    calls = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        return _ok(cmd, {"id": "sbx-1", "state": "started"})

    client = OneDaytonaClient(
        "live::daytona::default::test",
        runner=OneCli(runner=runner),
        dockerfile="FROM ubuntu:22.04",
        snapshot="",
    )
    client.create({"name": "named-only"})
    created = _execute_data(next(c for c in calls if "-d" in c))
    assert created["name"] == "named-only"
    assert created["buildInfo"]["dockerfileContent"] == "FROM ubuntu:22.04"
    assert "snapshot" not in created
    assert "--skip-validation" not in calls[0]


def test_tracer_creates_and_deletes_one_sandbox():
    calls = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        if cmd[2:4] == ["actions", "search"]:
            return _ok(cmd, {"actions": [{"actionId": "act-delete"}]})
        if "execute" in cmd:
            if "-d" in cmd:
                return _ok(cmd, {"id": "sbx-one", "state": "started"})
            return _ok(cmd, {"ok": True})
        return _ok(cmd, {"ok": True})

    settings = Settings(
        mock_mode=True,
        one_secret="sk-test",
        one_cli_auth=False,
        one_daytona_connection_key="live::daytona::default::test",
        daytona_sandbox_runs=True,
        sandbox_provider="auto",
    )
    one_client = OneDaytonaClient(
        settings.one_daytona_connection_key,
        runner=OneCli(runner=runner),
        delete_action_id="act-delete",
    )
    tracer = DaytonaTracer(settings, run_id="run-abcd-1", one_client=one_client)
    assert tracer.sandbox is not None
    assert tracer.sandbox.id == "sbx-one"
    assert any(r["name"] == "daytona.sandbox_created" for r in tracer.records())
    create_cmd = next(c for c in calls if c[2:4] == ["actions", "execute"] and "-d" in c)
    created = _execute_data(create_cmd)
    assert created["name"] == "cubiczan-outreach-run-abcd"
    assert created["buildInfo"]["dockerfileContent"] == DEFAULT_DAYTONA_DOCKERFILE
    assert created["snapshot"] == DEFAULT_DAYTONA_SNAPSHOT
    assert "--skip-validation" not in create_cmd
    tracer.close()
    assert tracer.sandbox is None
    assert any(c[2:4] == ["actions", "execute"] and c[5] == "act-delete" for c in calls)


def test_build_tracer_one_vs_none():
    one_settings = Settings(
        one_secret="sk-test",
        one_daytona_connection_key="live::daytona::default::test",
        daytona_sandbox_runs=False,
        one_cli_auth=False,
    )
    tracer = build_tracer(one_settings)
    assert isinstance(tracer, DaytonaTracer)
    assert one_settings.effective_sandbox_provider == "one"

    none_settings = Settings(one_cli_auth=False)
    assert none_settings.effective_sandbox_provider == "none"
    assert isinstance(build_tracer(none_settings), LoggingTracer)


def test_from_settings_wires_create_defaults():
    calls = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        return _ok(cmd, {"id": "sbx-settings", "state": "started"})

    settings = Settings(
        one_daytona_connection_key="live::daytona::default::test",
        one_daytona_dockerfile="FROM ubuntu:22.04",
        one_daytona_snapshot="",
        one_cli_auth=False,
    )
    client = one_daytona_from_settings(settings, runner=OneCli(runner=runner))
    sandbox = client.create()
    assert sandbox.id == "sbx-settings"
    created = _execute_data(next(c for c in calls if "-d" in c))
    assert created["buildInfo"]["dockerfileContent"] == "FROM ubuntu:22.04"
    assert "snapshot" not in created
    assert "--skip-validation" not in calls[0]


def test_sandbox_provider_daytona_skips_one():
    settings = Settings(
        sandbox_provider="daytona",
        one_secret="sk-test",
        one_daytona_connection_key="live::daytona::default::test",
        daytona_api_key="dtn-key",
        one_cli_auth=False,
    )
    assert settings.effective_sandbox_provider == "daytona"


def test_merge_sandbox_create_body_optional_target():
    body = merge_sandbox_create_body({"name": "n"}, target="eu")
    assert body["target"] == "eu"
    omitted = merge_sandbox_create_body({"name": "n"}, target="")
    assert "target" not in omitted
    caller = merge_sandbox_create_body({"name": "n", "target": "us"}, target="eu")
    assert caller["target"] == "us"


def test_one_daytona_import_avoids_outreach_store_cycle():
    src = str(Path(__file__).resolve().parents[1] / "src")
    env = os.environ.copy()
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from self_improving_outreach.tools.one_daytona import one_daytona_from_settings\n"
            "from self_improving_outreach.stores.base import OutreachStore\n"
            "assert one_daytona_from_settings is not None\n"
            "assert OutreachStore is not None\n",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_tracer_one_from_settings_does_not_circular_import():
    settings = Settings(
        one_secret="sk-test",
        one_daytona_connection_key="live::daytona::default::test",
        daytona_sandbox_runs=False,
        sandbox_provider="auto",
        one_cli_auth=False,
    )
    tracer = DaytonaTracer(settings, run_id="run-import-1")
    names = [r["name"] for r in tracer.records()]
    assert "daytona.client_ready" in names
    assert "daytona.init_failed" not in names
    assert tracer.client is not None
    ready = next(r for r in tracer.records() if r["name"] == "daytona.client_ready")
    assert ready["attributes"]["provider"] == "one"


def _install_fake_daytona(monkeypatch, *, create_error=None):
    created: dict = {}

    class FakeSandbox:
        def __init__(self):
            self.id = "sbx-sdk"
            self.deleted = False

        def delete(self):
            self.deleted = True

    class FakeConfig:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
            created["config"] = self

    class FakeCreateParams:
        model_fields = {"name": object(), "target": object()}

        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
            created["params"] = self

    class FakeDaytona:
        def __init__(self, config):
            self.config = config
            created["client"] = self

        def create(self, params=None, **kwargs):
            if create_error:
                raise RuntimeError(create_error)
            created["create_args"] = (params, kwargs)
            sandbox = FakeSandbox()
            created["sandbox"] = sandbox
            return sandbox

        def close(self):
            created["closed"] = True

    fake = types.ModuleType("daytona")
    fake.Daytona = FakeDaytona
    fake.DaytonaConfig = FakeConfig
    fake.CreateSandboxFromSnapshotParams = FakeCreateParams
    monkeypatch.setitem(sys.modules, "daytona", fake)
    return created


def test_sdk_create_passes_explicit_target(monkeypatch):
    created = _install_fake_daytona(monkeypatch)
    settings = Settings(
        sandbox_provider="daytona",
        daytona_api_key="dtn-key",
        daytona_target="us",
        daytona_sandbox_runs=True,
        one_cli_auth=False,
    )
    tracer = DaytonaTracer(settings, run_id="run-sdk-1")
    names = [r["name"] for r in tracer.records()]
    assert "daytona.client_ready" in names
    assert "daytona.sandbox_created" in names
    assert "daytona.init_failed" not in names
    assert created["config"].target == "us"
    assert created["config"].otel_enabled is False
    assert tracer.sandbox is not None
    assert tracer.sandbox.id == "sbx-sdk"
    ready = next(r for r in tracer.records() if r["name"] == "daytona.client_ready")
    assert ready["attributes"]["provider"] == "daytona"
    assert ready["attributes"]["target"] == "us"
    tracer.close()
    assert tracer.sandbox is None
    assert created["sandbox"].deleted is True
    assert created.get("closed") is True


def test_sdk_region_alias_and_create_failure_event(monkeypatch):
    created = _install_fake_daytona(
        monkeypatch,
        create_error="Failed to create sandbox: This organization does not have a default region.",
    )
    settings = Settings(
        sandbox_provider="daytona",
        daytona_api_key="dtn-key",
        daytona_region="eu",
        daytona_sandbox_runs=True,
        one_cli_auth=False,
    )
    assert settings.resolved_daytona_target == "eu"
    tracer = DaytonaTracer(settings, run_id="run-sdk-2")
    assert created["config"].target == "eu"
    assert tracer.sandbox is None
    failed = next(r for r in tracer.records() if r["name"] == "daytona.init_failed")
    assert failed["attributes"]["provider"] == "daytona"
    assert "default region" in failed["attributes"]["error"]
    assert any(r["name"] == "daytona.client_ready" for r in tracer.records())


def test_otel_unreachable_localhost_does_not_fail_or_hang(monkeypatch):
    created = _install_fake_daytona(monkeypatch)

    def _refuse(*_args, **_kwargs):
        raise OSError("Connection refused")

    monkeypatch.setattr("self_improving_outreach.observability.tracing.socket.create_connection", _refuse)
    settings = Settings(
        sandbox_provider="daytona",
        daytona_api_key="dtn-key",
        daytona_otel_enabled=True,
        daytona_sandbox_runs=True,
        one_cli_auth=False,
    )
    tracer = DaytonaTracer(settings, run_id="run-otel-1")
    with tracer.span("local.work"):
        pass
    names = [r["name"] for r in tracer.records()]
    assert "daytona.otel_disabled" in names
    assert "daytona.client_ready" in names
    assert "daytona.sandbox_created" in names
    assert "daytona.init_failed" not in names
    assert created["config"].otel_enabled is False
    assert any(r["name"] == "local.work" and r["phase"] == "ok" for r in tracer.records())


def test_from_settings_wires_target():
    calls = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        return _ok(cmd, {"id": "sbx-target", "state": "started"})

    settings = Settings(
        one_daytona_connection_key="live::daytona::default::test",
        daytona_target="us",
        one_cli_auth=False,
    )
    client = one_daytona_from_settings(settings, runner=OneCli(runner=runner))
    client.create({"name": "named"})
    created = _execute_data(next(c for c in calls if "-d" in c))
    assert created["target"] == "us"
