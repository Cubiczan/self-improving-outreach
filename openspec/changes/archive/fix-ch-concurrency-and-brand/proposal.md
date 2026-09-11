# Proposal: ClickHouse thread safety, brand critic, migrate DB bootstrap

## Why

A live swarm (`--concurrency 3`) failed workers with `ProgrammingError: Attempt to execute concurrent queries within the same session` because `ClickHouseStore` shared one `clickhouse_connect` client across `ThreadPoolExecutor` threads. Separately, Critic flagged correct **Cubiczan** drafts as brand misspellings (`CubicZan` is the same letters case-insensitively). Migrate also could not apply DDL when ClickHouse Cloud had no `outreach` database yet.

## What

- Give `ClickHouseStore` thread-local clients (`threading.local()` + per-thread factory). Leave `MemoryStore` unchanged.
- Check brand with case-sensitive `CubicZan` / spaced `Cubic Zan`; accept `Cubiczan`.
- `migrate` runs `CREATE DATABASE IF NOT EXISTS` on a connection that does not require the app database to already exist, then applies table DDL.

## Scope

In: ClickHouse store concurrency, critic brand helper, migrate CLI, tests, specs.

Out: secrets, MemoryStore behavior, LinkedIn send.
