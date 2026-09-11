# Learning Loop Specification

## Purpose

Update ICP scoring weights and winning message patterns from explicit and implicit outcomes so later drafts prefer angles that worked.

## Requirements

### Requirement: Outcome ingestion

The Learner SHALL accept explicit outcomes (`thumbs_up`, `thumbs_down`, `replied`, `meeting`, `ignore`, `sent`) and implicit signals (tool failure → failover path).

#### Scenario: CLI learn event

- GIVEN an existing lead and draft
- WHEN `python -m self_improving_outreach learn --event '{"lead_id":"...","outcome":"meeting"}'`
- THEN `icp_weights` and `message_patterns` are updated in ClickHouse or the in-memory store

#### Scenario: Positive outcome boosts matching features

- GIVEN a meeting booked for a CFO-titled lead using the material-weakness angle
- WHEN Learner runs
- THEN `cfo_cio_title` and related ICP weights increase
- AND that message pattern's win rate increases

### Requirement: Drafter reads memory

Drafter SHALL load current `message_patterns` ordered by score and SHALL prefer higher-scoring Cubiczan angles when composing the next draft.

#### Scenario: Next draft uses updated weights

- GIVEN a prior `replied` outcome for angle A
- WHEN a subsequent lead is drafted
- THEN Drafter selects angle A over lower-scoring alternatives unless Critic rejects it

### Requirement: Persistence fallback

If ClickHouse is unavailable, the system SHALL keep the same learning semantics in an in-memory (or local JSON queue) store so mock mode still learns.

### Requirement: LiveKit / voice preference interviews

Marketing Hunter or an AE MAY run a preference interview (LiveKit or a saved transcript) and feed the Learner. Pipeline Scout still owns LinkedIn send. Voice ingest SHALL work in mock mode without LiveKit keys.

#### Scenario: CLI transcript file

- GIVEN a lead and a JSON transcript with positive/negative, notes, and optional `pattern_id`
- WHEN `python -m self_improving_outreach voice --lead-id <id> --transcript-file path.json`
- THEN the Learner applies thumbs up/down
- AND an `outreach_event` is stored with `metadata.source=livekit`

#### Scenario: Post-draft auto hook

- GIVEN `LIVEKIT_FEEDBACK_AUTO=true` and `LIVEKIT_TRANSCRIPT_PATH` pointing at a file or a directory of `{lead_id}.json`
- WHEN the pipeline draft succeeds
- THEN the system parses that transcript and calls `record_voice_feedback`

#### Scenario: Mock voice without LiveKit

- GIVEN no `LIVEKIT_API_KEY`
- WHEN `voice --lead-id --positive` or `--transcript-file` is used
- THEN feedback is recorded without starting a LiveKit session

### Requirement: Opt-in learn on draft

After a successful draft / `approved_for_scout`, the pipeline SHALL call `simulate_outcome` and `apply_learn_event` when `LEARN_ON_DRAFT=true`, `MOCK_LEARN_OUTCOMES=true`, `swarm --learn-simulated`, or when mock-style simulate is enabled (`SIMULATE_OUTCOMES=true` and mock mode). Production live mode SHALL default to learn-from-real-outcomes only. Real replies, meetings, and ignores SHALL come from Pipeline Scout, ClickUp, LiveKit / `voice`, or `learn --event`.

#### Scenario: Demo live path learns on draft

- GIVEN `LEARN_ON_DRAFT=true` and `MOCK_MODE=false`
- WHEN a lead draft succeeds
- THEN `learned` is true
- AND ICP weights and the chosen message pattern are updated

#### Scenario: Production live path waits for Scout

- GIVEN `MOCK_MODE=false` and no `LEARN_ON_DRAFT` / `MOCK_LEARN_OUTCOMES`
- WHEN a lead draft succeeds with no explicit `--outcome`
- THEN the pipeline SHALL NOT simulate an outcome
- AND `learned` remains false unless LiveKit auto feedback applies

#### Scenario: LiveKit auto stub without transcript path

- GIVEN `LIVEKIT_FEEDBACK_AUTO=true`, LiveKit URL/key/secret set, and no transcript file
- WHEN the pipeline draft succeeds
- THEN the preference-interview stub writes a Learner event with `metadata.source=livekit`

### Requirement: Scout learn CLI

`python -m self_improving_outreach learn` SHALL accept Scout outcomes `thumbs_up`, `thumbs_down`, `replied`, `meeting`, `ignore`, and `sent`. If the lead is missing from the store, the CLI SHALL resolve it from the sample queue when present.

#### Scenario: Meeting outcome via CLI

- GIVEN a sample CFO lead
- WHEN `learn --event '{"lead_id":"...","outcome":"meeting","pattern_id":"mw-90d"}'`
- THEN matching ICP weights increase and the pattern win rate increases
