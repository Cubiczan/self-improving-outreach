# Design

## Thread-local ClickHouse clients

`clickhouse_connect` sessions are not thread-safe. Swarm workers share one `ClickHouseStore` instance (same as `MemoryStore`), so the store — not the orchestrator — must isolate sessions.

`ThreadLocalClients` wraps a `client_factory`. The first `query`/`insert`/`command` on a thread calls the factory and caches the client on `threading.local()`. `from_settings` passes a factory that calls `get_client(...)` so each worker gets its own HTTP session. Tests inject a factory that returns a new fake session sharing in-memory tables.

`_ensure_seed` stays process-wide with a lock so default weights/patterns insert once. Seed data lives in the database, not on the session.

A process-wide lock around every client op would also fix the crash but would serialize the swarm's I/O. Thread-local clients keep concurrency.

## Brand critic

`CubicZan`.lower() == `Cubiczan`.lower(), so case-insensitive substring checks treat the correct brand as a misspelling. Detection is case-sensitive for `CubicZan` / `cubicZan`, and regex `cubic\s+zan` (case-insensitive) for the spaced form, which cannot match `Cubiczan`. Rewrite replaces those forms with `Cubiczan` only.

## Migrate bootstrap

`ClickHouseStore.from_settings` selects `CLICKHOUSE_DATABASE` on connect. If that database is missing, the handshake fails before `001_init.sql` can run `CREATE DATABASE IF NOT EXISTS`. Migrate connects without selecting the app database, issues `CREATE DATABASE IF NOT EXISTS <ident>`, then applies the SQL file (idempotent `IF NOT EXISTS` DDL). Identifiers are restricted to `[A-Za-z_][A-Za-z0-9_]*`.
