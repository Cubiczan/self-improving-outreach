# Learning Loop Specification

## ADDED Requirements

### Requirement: Opt-in learn on draft

After a successful draft / `approved_for_scout`, the pipeline SHALL call `simulate_outcome` and `apply_learn_event` when `LEARN_ON_DRAFT=true`, or when mock-style simulate is enabled (`SIMULATE_OUTCOMES=true` and mock mode). Production live mode SHALL default to learn-from-real-outcomes only (`LEARN_ON_DRAFT=false`).

#### Scenario: Demo live path learns on draft

- GIVEN `LEARN_ON_DRAFT=true` and `MOCK_MODE=false`
- WHEN a lead draft succeeds
- THEN `learned` is true
- AND ICP weights and the chosen message pattern are updated

#### Scenario: Production live path waits for Scout

- GIVEN `MOCK_MODE=false` and `LEARN_ON_DRAFT=false`
- WHEN a lead draft succeeds with no explicit `--outcome`
- THEN the pipeline SHALL NOT simulate an outcome
- AND `learned` remains false unless LiveKit auto feedback applies

### Requirement: Scout learn CLI

`python -m self_improving_outreach learn` SHALL accept Scout outcomes `thumbs_up`, `thumbs_down`, `replied`, `meeting`, `ignore`, and `sent`. If the lead is missing from the store, the CLI SHALL resolve it from the sample queue when present.

#### Scenario: Meeting outcome via CLI

- GIVEN a sample CFO lead
- WHEN `learn --event '{"lead_id":"...","outcome":"meeting","pattern_id":"mw-90d"}'`
- THEN matching ICP weights increase and the pattern win rate increases
