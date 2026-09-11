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
