# Outreach Pipeline Specification

## ADDED Requirements

### Requirement: Optional draft-time learner

The closed loop MAY update the Learner immediately after a successful draft when `LEARN_ON_DRAFT` or mock simulate is enabled. Otherwise Learner updates wait for an explicit `learn` event or optional LiveKit auto transcript.

#### Scenario: Mock swarm still demonstrates learning

- GIVEN `MOCK_MODE=true` and `SIMULATE_OUTCOMES=true`
- WHEN `swarm --once` completes a batch
- THEN simulated outcomes update weights and patterns for the next batch
