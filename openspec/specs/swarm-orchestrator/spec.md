# Swarm Orchestrator Specification

## Purpose

Run N parallel closed-loop crews over a lead queue without letting a single worker or tool failure kill the swarm.

## Requirements

### Requirement: Configurable concurrency

The swarm SHALL pull queued leads from ClickHouse (or a local JSON queue in mock mode) and process them with configurable worker concurrency.

#### Scenario: One-shot swarm

- GIVEN a JSON queue with 2–3 leads and no API keys
- WHEN `python -m self_improving_outreach swarm --once --concurrency 2`
- THEN each lead completes the closed loop
- AND the process exits with a summary

#### Scenario: Continuous loop

- GIVEN `--loop --interval 300`
- WHEN the swarm is running
- THEN it waits `interval` seconds between batches until interrupted

### Requirement: Thread-safe ClickHouse access

When the swarm uses `ClickHouseStore`, concurrent workers SHALL NOT share a single `clickhouse_connect` session. The store SHALL give each thread its own client (thread-local / per-worker factory). `MemoryStore` locking is unchanged.

#### Scenario: Concurrent swarm against ClickHouse

- GIVEN `swarm --concurrency 3` and a configured ClickHouse store
- WHEN workers upsert and list in parallel
- THEN the run SHALL NOT fail with concurrent-query-in-the-same-session errors
- AND each worker thread uses a separate client instance

### Requirement: Worker isolation

A tool failure in one worker SHALL switch that worker to its failover path, log `tool_failures` and Daytona/trace spans, and SHALL NOT cancel other workers.

#### Scenario: You.com outage on one lead

- GIVEN three queued leads and a You.com client that fails for one query
- WHEN the swarm runs
- THEN the failed worker degrades to cached context
- AND the other leads still produce drafts
- AND the swarm exit status is success if at least the remaining units completed

### Requirement: Cross-batch learning

After a batch logs outcomes, the next batch SHALL read updated ICP weights and message patterns.

#### Scenario: Better angles in the next batch

- GIVEN batch 1 records a `replied` on the treasury-observability angle
- WHEN batch 2 drafts
- THEN Drafter prefers that winning pattern
