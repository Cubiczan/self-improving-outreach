# CHP Decision Lock Specification

## Purpose

Govern Self Improving Outreach drafts with Cubiczan Consensus Hardening Protocol (CHP) so Pipeline Scout only receives a lead after a sealed R0 foundation, a non-skippable structural adversary, a named human lock, and an immutable evidence pack.

## Requirements

### Requirement: Feature flag defaults true on live

The system SHALL read `CHP_LOCK_ENABLED`. When unset, the resolved flag SHALL be true if `is_mock` is false, otherwise false. Explicit true or false SHALL win. Mock CI without the env var SHALL keep the pre-CHP gate path.

#### Scenario: Live default requires the lock

- GIVEN `MOCK_MODE=false` and live LLM + research credentials
- AND `CHP_LOCK_ENABLED` is unset
- WHEN Settings resolve
- THEN `resolved_chp_lock_enabled` is true

#### Scenario: Mock default leaves the stub gate

- GIVEN `MOCK_MODE=true` and `CHP_LOCK_ENABLED` unset
- WHEN a lead completes critic
- THEN the unit MAY reach `approved_for_scout` via the existing human-gate stub
- AND Score and Learner behavior SHALL be unchanged

### Requirement: Sealed R0 before peers see each other

When the flag is on, the system SHALL independently seal research, score, and draft payloads (each digest covers only that peer’s fields) and SHALL compose an R0 foundation commit from those seals before the adversary or human observes the envelope. The composed R0 SHALL be immutable.

#### Scenario: Peer seals do not include other peers

- GIVEN research, score, and draft outputs for one run
- WHEN R0 is committed
- THEN the research seal digest is computed without draft body or score totals
- AND the score seal digest is computed without draft body
- AND the draft seal digest is computed without research synthesis
- AND the R0 digest is the hash of the three peer digests plus the R0 gate result

#### Scenario: R0 cannot be rewritten after seal

- GIVEN a sealed R0 commit
- WHEN a caller attempts to change a peer payload or recompute a mismatched digest
- THEN the session SHALL reject the mutation
- AND later lock SHALL fail

### Requirement: Non-skippable structural adversary

When the flag is on, the system SHALL run a deterministic structural adversary against the sealed R0. The pass SHALL NOT be skippable. CrewAI adversary notes (PR 9) MAY be recorded as extras and SHALL NOT replace this pass.

#### Scenario: Adversary always runs when the flag is on

- GIVEN `CHP_LOCK_ENABLED=true` and a sealed R0
- WHEN the session advances
- THEN an adversary report is stored with `skippable=false`
- AND a request to skip the adversary SHALL fail

#### Scenario: Structural findings are recorded

- GIVEN a sealed draft that implies a LinkedIn send or uses CubicZan
- WHEN the adversary runs
- THEN the report lists those structural vulnerabilities
- AND the R0 digest on the report matches the sealed commit

### Requirement: Named human lock

Transition to `locked` SHALL require a named human actor and an explicit `approve` or `deny`. Empty actor names and reserved automations (`system`, `auto`, `anonymous`, `bot`) SHALL be rejected. Deny SHALL NOT mark the lead `approved_for_scout`.

#### Scenario: Approve with a named actor

- GIVEN a provisional session with sealed R0 (PASS) and an adversary report
- WHEN `chp lock --approve --actor "Sam Desigan"` runs
- THEN phase becomes `locked`
- AND the lock record stores that actor

#### Scenario: Anonymous lock is rejected

- GIVEN a provisional session
- WHEN lock is attempted with actor `auto` or an empty name
- THEN the session stays provisional
- AND no evidence pack is sealed

### Requirement: Immutable evidence pack before approved_for_scout

A pack SHALL hash the sealed R0, adversary report, and lock record. After seal, field mutation SHALL fail. When the flag is on, `approved_for_scout` SHALL require phase `locked` and a verified pack. The pipeline SHALL NOT auto-send LinkedIn or email.

#### Scenario: Pack seal is required to promote

- GIVEN a locked session with a verified pack
- WHEN promote-to-scout runs
- THEN lead status becomes `approved_for_scout`
- AND the pack digest still verifies

#### Scenario: Pipeline does not auto-approve when the flag is on

- GIVEN `CHP_LOCK_ENABLED=true`
- WHEN critic finishes
- THEN lead status is `provisional` (or earlier CHP phase)
- AND status is not `approved_for_scout`
- AND no LinkedIn or email send is invoked
