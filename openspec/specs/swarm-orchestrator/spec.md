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

A tool failure in one worker SHALL switch that worker to its failover path, log `tool_failures` and Daytona/trace spans, and SHALL NOT cancel other workers. Research MAY run through One `you` actions or the direct You.com client; the failover contract is the same.

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

### Requirement: Queue reclaim

The system SHALL provide a CLI (`requeue` and `queue reset`) that sets matching leads to `queued` so the swarm can claim them again. Selectors SHALL include `lead_id`, company (case-insensitive substring), `--all-sample` (the committed sample ICP queue), `--clear-processing` for stuck `processing` rows, and `--status processing|failed|done` (`done` means drafted / pending_review / approved_for_scout / learned). `swarm --requeue` SHALL reclaim `processing` and `failed` before claiming. The committed sample JSON file SHALL NOT be overwritten.

#### Scenario: Requeue by lead id

- GIVEN a lead whose status is `approved_for_scout`
- WHEN `requeue --lead-id <id>` runs
- THEN that lead's status is `queued`

#### Scenario: Requeue sample leads

- GIVEN `data/leads.sample.json`
- WHEN `requeue --all-sample` runs
- THEN the three sample ICP leads are upserted with status `queued`

#### Scenario: Clear stuck processing

- GIVEN a lead in `processing`
- WHEN `requeue --clear-processing` runs
- THEN that lead's status is `queued`

#### Scenario: Requeue by status and swarm reclaim

- GIVEN leads in `failed` or `approved_for_scout`
- WHEN `requeue --status failed` or `requeue --status done` runs
- THEN those leads have status `queued`
- AND `swarm --requeue --once` requeues `processing` and `failed` before claiming

### Requirement: ClickUp list poll

`clickup-sync` SHALL poll `CLICKUP_LIST_ID` (default Sales Leads `901716996906`) using `CLICKUP_API_TOKEN` and map tasks in `CLICKUP_QUEUE_STATUS` (default Queued) through the existing ClickUp mapper. Re-poll SHALL NOT reset an in-flight status. Tests SHALL use a mock client.

#### Scenario: Poll without token

- GIVEN no `CLICKUP_API_TOKEN`
- WHEN `clickup-sync` runs
- THEN the CLI exits 0 without calling ClickUp HTTP

### Requirement: ClickUp queue ingest

The system SHALL ingest a ClickUp task JSON or webhook envelope (`task` / `task_id`) into the lead queue as `queued` via `ingest-clickup` or `queue upsert --from-json`. Ingest SHALL run when the ClickUp status is `Queued` (case-insensitive) unless `--force`. This path is search + outreach only and SHALL NOT create Google Ads, Facebook Ads, or Meta Ads spend.

#### Scenario: CLI ingest of a Queued ClickUp task

- GIVEN a ClickUp task payload with status `Queued` and company/contact fields
- WHEN `ingest-clickup --file path.json` runs
- THEN a lead is upserted with status `queued` and a stable `clickup-{task_id}` (or explicit `lead_id`)

#### Scenario: Non-queued task is skipped

- GIVEN a ClickUp task whose status is `in progress`
- WHEN `ingest-clickup` runs without `--force`
- THEN no lead is written and the CLI reports skipped
