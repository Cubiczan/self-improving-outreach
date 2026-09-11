"""ClickHouseStore thread-local clients and migrate bootstrap (fake client, no secrets)."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from self_improving_outreach.config import Settings, reset_settings_cache
from self_improving_outreach.models import Lead, LeadStatus
from self_improving_outreach.stores.clickhouse import (
    ClickHouseStore,
    ThreadLocalClients,
    apply_clickhouse_migration,
    parse_sql_statements,
    quote_identifier,
)
from self_improving_outreach.stores.memory import MemoryStore

LEAD_COLUMNS = [
    "lead_id",
    "company",
    "domain",
    "contact_name",
    "title",
    "industry",
    "location",
    "signals",
    "cached_context",
    "status",
    "created_at",
    "updated_at",
]


class ProgrammingError(Exception):
    """Mirrors clickhouse_connect.driver.exceptions.ProgrammingError."""


class FakeQueryResult:
    def __init__(self, rows, column_names):
        self.result_rows = rows
        self.column_names = column_names


def _empty_state() -> dict:
    return {
        "lock": threading.Lock(),
        "leads": [],
        "icp_weights": [],
        "message_patterns": [],
        "outreach_events": [],
        "tool_failures": [],
        "agent_runs": [],
    }


class FakeClickHouseClient:
    """Session-guarded fake. Concurrent ops on the same instance raise ProgrammingError."""

    def __init__(self, state: dict) -> None:
        self._state = state
        self._busy = False
        self._session = threading.Lock()

    def _enter(self) -> None:
        with self._session:
            if self._busy:
                raise ProgrammingError(
                    "Attempt to execute concurrent queries within the same session. "
                    "Please use a separate client instance per thread/process."
                )
            self._busy = True
        time.sleep(0.01)

    def _exit(self) -> None:
        with self._session:
            self._busy = False

    def query(self, sql: str, parameters=None):
        self._enter()
        try:
            parameters = parameters or {}
            with self._state["lock"]:
                if "count()" in sql and "icp_weights" in sql:
                    return FakeQueryResult([[len(self._state["icp_weights"])]], ["c"])
                if "count()" in sql and "message_patterns" in sql:
                    return FakeQueryResult([[len(self._state["message_patterns"])]], ["c"])
                if "FROM leads" in sql:
                    rows = list(self._state["leads"])
                    if "lead_id" in sql and "id" in parameters:
                        rows = [row for row in rows if str(row[0]) == str(parameters["id"])]
                    if "status =" in sql and "s" in parameters:
                        rows = [row for row in rows if row[9] == parameters["s"]]
                    limit = int(parameters.get("lim", len(rows) or 50))
                    return FakeQueryResult(rows[:limit], LEAD_COLUMNS)
                return FakeQueryResult([], [])
        finally:
            self._exit()

    def insert(self, table: str, rows, column_names=None):
        self._enter()
        try:
            with self._state["lock"]:
                self._state.setdefault(table, []).extend(list(rows))
        finally:
            self._exit()

    def command(self, sql: str) -> None:
        self._enter()
        try:
            self._state.setdefault("commands", []).append(sql)
        finally:
            self._exit()


def test_thread_local_clients_one_instance_per_thread():
    created: list[object] = []
    lock = threading.Lock()

    def factory() -> object:
        obj = object()
        with lock:
            created.append(obj)
        return obj

    pool = ThreadLocalClients(factory)
    reuse: dict[int, bool] = {}
    ids: dict[int, int] = {}

    def worker(idx: int) -> None:
        first = pool.get()
        second = pool.get()
        reuse[idx] = first is second
        ids[idx] = id(first)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(created) == 3
    assert all(reuse.values())
    assert len(set(ids.values())) == 3


def test_clickhouse_store_concurrent_upserts_and_list():
    state = _empty_state()
    created: list[FakeClickHouseClient] = []
    lock = threading.Lock()

    def factory() -> FakeClickHouseClient:
        client = FakeClickHouseClient(state)
        with lock:
            created.append(client)
        return client

    store = ClickHouseStore(client_factory=factory, database="outreach")
    leads = [
        Lead(company=f"Co-{i}", contact_name="A", title="CFO", status=LeadStatus.QUEUED)
        for i in range(3)
    ]

    def work(lead: Lead) -> None:
        store.upsert_lead(lead)
        assert store.list_leads(limit=10)

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(work, leads))

    assert len(created) == 3
    assert len({id(client) for client in created}) == 3
    listed = store.list_leads(limit=10)
    assert len(listed) == 3
    assert {lead.company for lead in listed} == {"Co-0", "Co-1", "Co-2"}


def test_shared_client_fails_concurrent_queries():
    """Control: one shared session raises the production ProgrammingError."""
    state = _empty_state()
    client = FakeClickHouseClient(state)
    store = ClickHouseStore(client, "outreach")
    leads = [Lead(company=f"X-{i}", title="CFO") for i in range(3)]
    errors: list[BaseException] = []

    def work(lead: Lead) -> None:
        try:
            store.upsert_lead(lead)
        except ProgrammingError as exc:
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(work, leads))

    assert errors
    assert "separate client instance" in str(errors[0])


def test_memory_store_still_thread_safe_and_unchanged():
    store = MemoryStore()
    leads = [Lead(company=f"M-{i}", title="CFO") for i in range(3)]

    def work(lead: Lead) -> None:
        store.upsert_lead(lead)
        store.list_leads()

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(work, leads))

    assert len(store.list_leads(limit=10)) == 3


def test_apply_clickhouse_migration_creates_database_first(tmp_path: Path):
    sql_path = tmp_path / "001_init.sql"
    sql_path.write_text(
        "CREATE DATABASE IF NOT EXISTS outreach;\n"
        "CREATE TABLE IF NOT EXISTS outreach.leads (lead_id UUID) ENGINE = Memory;\n",
        encoding="utf-8",
    )
    settings = Settings(
        mock_mode=True,
        clickhouse_host="ch.example.invalid",
        clickhouse_database="outreach",
    )
    commands: list[str] = []
    connected: dict[str, object] = {}

    class Client:
        def command(self, sql: str) -> None:
            commands.append(sql)

    def connect(settings: Settings, database=None):
        connected["database"] = database
        connected["host"] = settings.clickhouse_host
        return Client()

    applied = apply_clickhouse_migration(settings, sql_path, connect=connect)
    assert connected["database"] == ""
    assert commands[0] == "CREATE DATABASE IF NOT EXISTS outreach"
    assert any("CREATE TABLE IF NOT EXISTS outreach.leads" in stmt for stmt in commands)
    assert applied == 2
    assert parse_sql_statements(sql_path.read_text(encoding="utf-8"))[0].startswith(
        "CREATE DATABASE"
    )


def test_quote_identifier_rejects_injection():
    assert quote_identifier("outreach") == "outreach"
    with pytest.raises(ValueError):
        quote_identifier("outreach; DROP DATABASE")
    with pytest.raises(ValueError):
        quote_identifier("")


def test_cli_migrate_bootstraps_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from typer.testing import CliRunner

    from self_improving_outreach.cli import app

    monkeypatch.setenv("CLICKHOUSE_HOST", "ch.example.invalid")
    monkeypatch.setenv("CLICKHOUSE_DATABASE", "outreach")
    reset_settings_cache()
    sql_path = tmp_path / "001.sql"
    sql_path.write_text("CREATE TABLE IF NOT EXISTS outreach.t (x String) ENGINE = Memory;", encoding="utf-8")
    seen: dict[str, object] = {}

    def fake_apply(settings, path, **kwargs):
        seen["database"] = settings.clickhouse_database
        seen["host"] = settings.clickhouse_host
        seen["path"] = Path(path)
        return 4

    monkeypatch.setattr(
        "self_improving_outreach.stores.clickhouse.apply_clickhouse_migration",
        fake_apply,
    )
    result = CliRunner().invoke(app, ["migrate", "--sql-path", str(sql_path)])
    assert result.exit_code == 0, result.stdout
    assert seen["database"] == "outreach"
    assert "Applied 4 statements to outreach" in result.stdout
    assert "password" not in result.stdout.lower()
