# Outreach Pipeline Specification

## ADDED Requirements

### Requirement: CHP lock owns send-readiness when enabled

When `resolved_chp_lock_enabled` is true, the closed loop SHALL execute research → score → draft → critic → R0 seal → structural adversary → provisional hold. It SHALL NOT set `approved_for_scout` in that same unit. Promotion SHALL wait for a named human lock and a verified evidence pack. Score totals and Learner weight updates SHALL remain deterministic Python.

#### Scenario: Live lock hold

- GIVEN `CHP_LOCK_ENABLED=true`
- WHEN `run` or a swarm worker finishes critic
- THEN the unit is stored as `provisional`
- AND `outreach_event` metadata records the CHP phase
- AND Learner MAY still apply opt-in draft outcomes
- AND the process does not send LinkedIn or email

## MODIFIED Requirements

### Requirement: Send ownership

The pipeline SHALL NOT send LinkedIn or email. When CHP lock is off, approved drafts are logged as ready for Marketing Hunter / Pipeline Scout (or `pending_review` if `HUMAN_GATE_ENABLED=true`). When CHP lock is on, Scout-ready status requires a locked evidence pack.

#### Scenario: Human-gate stub when CHP is off

- GIVEN `HUMAN_GATE_ENABLED=true` and `resolved_chp_lock_enabled` is false
- WHEN Critic accepts a draft
- THEN the unit is stored as `pending_review` rather than `approved_for_scout`

#### Scenario: CHP lock supersedes the stub

- GIVEN `CHP_LOCK_ENABLED=true` (even if `HUMAN_GATE_ENABLED=false`)
- WHEN Critic accepts a draft
- THEN the unit is not `approved_for_scout` until named lock + verified pack
