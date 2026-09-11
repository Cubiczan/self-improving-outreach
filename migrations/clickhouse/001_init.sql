-- Cubiczan outreach learning schema. Apply with:
--   python -m self_improving_outreach migrate
-- Local: docker compose up -d && CLICKHOUSE_HOST=localhost CLICKHOUSE_PORT=8123 ...

CREATE DATABASE IF NOT EXISTS outreach;

CREATE TABLE IF NOT EXISTS outreach.leads
(
    lead_id UUID,
    company String,
    domain String,
    contact_name String,
    title String,
    industry String,
    location String,
    signals String,
    cached_context String,
    status LowCardinality(String),
    created_at DateTime64(3),
    updated_at DateTime64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (lead_id);

CREATE TABLE IF NOT EXISTS outreach.outreach_events
(
    event_id UUID,
    lead_id UUID,
    run_id UUID,
    channel LowCardinality(String),
    outcome LowCardinality(String),
    angle String,
    pattern_id String,
    body String,
    metadata String,
    created_at DateTime64(3)
)
ENGINE = MergeTree
ORDER BY (created_at, lead_id);

CREATE TABLE IF NOT EXISTS outreach.message_patterns
(
    pattern_id String,
    angle String,
    channel LowCardinality(String),
    template String,
    wins UInt64,
    losses UInt64,
    impressions UInt64,
    score Float64,
    updated_at DateTime64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (pattern_id);

CREATE TABLE IF NOT EXISTS outreach.icp_weights
(
    feature String,
    weight Float64,
    updated_at DateTime64(3),
    version UInt64
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (feature);

CREATE TABLE IF NOT EXISTS outreach.tool_failures
(
    failure_id UUID,
    run_id String,
    tool_name String,
    error_class String,
    message String,
    retry_attempt UInt8,
    degraded UInt8,
    created_at DateTime64(3)
)
ENGINE = MergeTree
ORDER BY (created_at, tool_name);

CREATE TABLE IF NOT EXISTS outreach.agent_runs
(
    run_id UUID,
    swarm_id String,
    lead_id UUID,
    status LowCardinality(String),
    traces String,
    worker_id String,
    error String,
    started_at DateTime64(3),
    finished_at DateTime64(3)
)
ENGINE = MergeTree
ORDER BY (started_at, run_id);
