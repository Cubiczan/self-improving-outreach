# ClickHouse Persistence Specification

## Purpose

Persist leads, events, patterns, weights, tool failures, agent runs, and CHP decisions in ClickHouse when configured. Fall back to the in-memory store without changing MemoryStore semantics.

## Requirements

### Requirement: Per-thread ClickHouse sessions

`ClickHouseStore` SHALL create `clickhouse_connect` clients via a factory and cache one client per thread (`threading.local()`). Sharing one client across `ThreadPoolExecutor` workers is forbidden.

#### Scenario: Thread-local clients

- GIVEN a `ClickHouseStore` built from a client factory
- WHEN two threads each perform a query
- THEN the factory is invoked once per thread
- AND a second call on the same thread reuses that thread's client

### Requirement: Migrate bootstraps a missing database

`python -m self_improving_outreach migrate` SHALL issue `CREATE DATABASE IF NOT EXISTS` for `CLICKHOUSE_DATABASE` on a connection that does not require that database to already exist, then apply table DDL.

#### Scenario: Empty ClickHouse Cloud (no outreach database)

- GIVEN ClickHouse is configured and database `outreach` does not exist
- WHEN migrate runs
- THEN the database is created
- AND `001_init.sql` table statements are applied
- AND `002_chp_lock.sql` (`chp_decisions`) is applied when migrate is pointed at the migrations directory

### Requirement: CHP decisions table

When ClickHouse is configured, the store SHALL persist CHP sessions in `chp_decisions` (decision id, lead id, run id, phase, digests, actor, JSON payload). MemoryStore SHALL keep the same save/get semantics in process. A jsonl file (`CHP_DECISIONS_PATH`) SHALL allow a later CLI process to lock a mock run.

#### Scenario: Memory save and get

- GIVEN a sealed provisional decision
- WHEN the store saves it
- THEN `get_chp_decision(lead_id)` returns the same phase and R0 digest
