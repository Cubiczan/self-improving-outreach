# Outreach Pipeline Specification

## Purpose

Run a Cubiczan-branded CrewAI crew (or a deterministic mock of the same stages) that researches a lead, scores ICP fit, drafts LinkedIn/email follow-up, self-critiques, and holds send for Pipeline Scout.

## Requirements

### Requirement: Closed-loop unit of work

The system SHALL execute each lead through: research → score → draft → critic → human-gate stub → log `outreach_event` → optional learner update (`LEARN_ON_DRAFT`, mock `SIMULATE_OUTCOMES`, explicit `learn`, or LiveKit auto transcript).

#### Scenario: Mock mode with no API keys

- GIVEN no You.com, Daytona, LiveKit, ClickHouse, or LLM keys
- WHEN `python -m self_improving_outreach run --lead "..."` is invoked
- THEN the pipeline completes using mocked research and an in-memory store

#### Scenario: Live CrewAI via Boundless

- GIVEN `MOCK_MODE=false`, `LLM_PROVIDER=boundless`, and `BOUNDLESS_API_KEY`
- WHEN `swarm --once` runs and the `crew` extra is installed
- THEN Drafter MAY call CrewAI against the Boundless OpenAI-compatible `base_url`
- AND if CrewAI or the LLM call fails, the deterministic drafter still completes the unit

#### Scenario: Live web refresh before draft

- GIVEN a You.com API key (or One You auth + `ONE_YOU_CONNECTION_KEY`)
- WHEN a lead is processed
- THEN Researcher SHALL call You.com Search and/or Research (via One `you` actions when that is the effective provider, otherwise the direct HTTP client) before Drafter runs
- AND if You.com fails twice, Researcher SHALL degrade to cached ClickHouse/in-memory context and log `tool_failures`

#### Scenario: Live web refresh via One

- GIVEN One auth, `ONE_YOU_CONNECTION_KEY`, `MOCK_MODE=false`, and `RESEARCH_PROVIDER=auto`
- WHEN a lead is processed
- THEN Researcher SHALL execute One `you` Search/Research before Drafter runs
- AND if that call fails twice, Researcher SHALL degrade to cached context and log `tool_failures`

### Requirement: Cubiczan brand constraints

Drafts SHALL use the brand spelling **Cubiczan** (never CubicZan or Cubic Zan) and SHALL reflect governed multi-agent finance positioning (close, reconciliation, treasury, observability) and 90-day material-weakness remediation. Founder attribution SHALL be Sam/Shyam Desigan.

Critic brand checks SHALL treat **Cubiczan** as correct and SHALL NOT flag it as a misspelling of CubicZan (those strings differ only by the letter Z and MUST NOT be compared case-insensitively). Forbidden forms are the case-sensitive token CubicZan and the spaced form Cubic Zan (any spacing/casing of `cubic` + whitespace + `zan`).

#### Scenario: Critic accepts correct Cubiczan spelling

- GIVEN a draft whose body contains "Cubiczan" and does not contain "CubicZan" or "Cubic Zan"
- WHEN Critic runs
- THEN it SHALL NOT report "brand misspelling"
- AND the draft may be accepted if no other issues apply

#### Scenario: Critic rejects brand misspelling

- GIVEN a draft containing "CubicZan" or "Cubic Zan"
- WHEN Critic runs
- THEN the draft is revised to Cubiczan and flagged before it is logged as ready for scout

### Requirement: Send ownership

The pipeline SHALL NOT send LinkedIn or email. Approved drafts are logged as ready for Marketing Hunter / Pipeline Scout.

#### Scenario: Human-gate stub

- GIVEN `HUMAN_GATE_ENABLED=true`
- WHEN Critic accepts a draft
- THEN the unit is stored as `pending_review` rather than `approved_for_scout`

### Requirement: Optional draft-time learner

The closed loop MAY update the Learner immediately after a successful draft when `LEARN_ON_DRAFT` or mock simulate is enabled. Otherwise Learner updates wait for an explicit `learn` event or optional LiveKit auto transcript.

#### Scenario: Mock swarm still demonstrates learning

- GIVEN `MOCK_MODE=true` and `SIMULATE_OUTCOMES=true`
- WHEN `swarm --once` completes a batch
- THEN simulated outcomes update weights and patterns for the next batch
