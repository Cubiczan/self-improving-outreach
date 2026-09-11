# Swarm Orchestrator Specification

## ADDED Requirements

### Requirement: Queue reclaim

The system SHALL provide a CLI (`requeue` and `queue reset`) that sets matching leads to `queued` so the swarm can claim them again. Selectors SHALL include `lead_id`, company (case-insensitive substring), `--all-sample` (the committed sample ICP queue), and optional `--clear-processing` for stuck `processing` rows. The committed sample JSON file SHALL NOT be overwritten.

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
