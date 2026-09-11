-- CHP decision lock sessions. Apply after 001_init.sql.

CREATE TABLE IF NOT EXISTS outreach.chp_decisions
(
    decision_id UUID,
    lead_id UUID,
    run_id UUID,
    phase LowCardinality(String),
    r0_digest String,
    pack_digest String,
    actor String,
    payload String,
    created_at DateTime64(3),
    updated_at DateTime64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (lead_id, decision_id);
