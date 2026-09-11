# ClickHouse Persistence Specification

## ADDED Requirements

### Requirement: CHP decisions table

When ClickHouse is configured, the store SHALL persist CHP sessions in `chp_decisions` (decision id, lead id, run id, phase, digests, actor, JSON payload). MemoryStore SHALL keep the same save/get semantics in process. A jsonl file (`CHP_DECISIONS_PATH`) SHALL allow a later CLI process to lock a mock run.

#### Scenario: Memory save and get

- GIVEN a sealed provisional decision
- WHEN the store saves it
- THEN `get_chp_decision(lead_id)` returns the same phase and R0 digest
