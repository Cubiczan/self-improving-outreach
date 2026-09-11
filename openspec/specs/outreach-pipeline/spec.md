# Outreach Pipeline Specification

## Purpose

Run Self Improving Outreach — a Cubiczan-branded closed loop for **any outbound sales** (not CFO/CIO-only). CrewAI MAY draft prose inside each swarm worker. Deterministic Python owns ICP Score math, Learner updates, and the code brand critic. When CHP lock is on, send-readiness is owned by sealed R0 + structural adversary + named human lock + evidence pack. CrewAI SHALL NOT bypass that lock. Pipeline Scout owns send.

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
- AND the code brand critic still runs after CrewAI returns a body

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

### Requirement: CrewAI utilization modes

The system SHALL read `CREWAI_MODE=off|draft|full`. When unset, the resolved mode SHALL be `full` if `use_crewai` is true, otherwise `off`. Mock mode and missing LLM credentials SHALL resolve to `off` so the no-keys CI path is unchanged.

#### Scenario: Default full when live CrewAI is on

- GIVEN `MOCK_MODE=false` and an LLM key
- WHEN Settings resolve
- THEN `use_crewai` is true
- AND `resolved_crewai_mode` is `full`

#### Scenario: Draft compatibility mode

- GIVEN `CREWAI_MODE=draft`, `MOCK_MODE=false`, and an LLM key
- WHEN CrewAI runs
- THEN the crew is sequential Researcher → Interpreter Scorer → Drafter → Critic
- AND no You.com or memory tools are attached
- AND only the draft body is replaced

#### Scenario: Full mode attaches tools and richer roles

- GIVEN `CREWAI_MODE=full` (or default) and live CrewAI
- WHEN the crew is assembled
- THEN Researcher HAS a You.com search tool so it MAY refresh research mid-crew
- AND a Strategist agent picks a scored `message_patterns` angle without inventing weights
- AND an Adversary Critic argues against weak claims, compliance/send risks, and overclaims
- AND an Interpreter Scorer MAY explain the deterministic score without recomputing it

#### Scenario: CrewAI failure still completes the unit

- GIVEN live CrewAI is selected
- WHEN CrewAI is missing or kickoff fails
- THEN the deterministic drafter still completes the unit
- AND the tracer records `crewai.fallback`

### Requirement: CrewAI does not own Score, Learner, or send-readiness

ICP Score numbers SHALL come from stored ClickHouse (or in-memory) weights. Learner weight and pattern updates SHALL stay on the deterministic outcome path. CrewAI SHALL NOT write `icp_weights` or invent pattern scores. Strategist, Adversary Critic, You.com tools, and `CREWAI_MODE` SHALL only affect draft prose. They SHALL NOT set `approved_for_scout`, skip R0, skip the structural adversary, seal a human lock, or mutate the evidence pack. When `resolved_chp_lock_enabled` is true, a `full` or `draft` CrewAI unit SHALL still stop at `provisional` until named lock + verified pack. CrewAI adversary notes MAY be recorded on the structural adversary report as extras.

#### Scenario: Full mode still uses deterministic score

- GIVEN a lead is processed in `full` mode
- WHEN Scorer / Interpreter runs
- THEN the numeric total and weights are those already computed in Python
- AND the code brand critic still runs after CrewAI returns a body

#### Scenario: Full mode still holds for CHP lock

- GIVEN `CREWAI_MODE=full` and `CHP_LOCK_ENABLED=true`
- WHEN a lead finishes the CrewAI Adversary Critic and the code critic
- THEN lead status is `provisional`
- AND a structural adversary report exists with `skippable=false`
- AND status is not `approved_for_scout`

### Requirement: CrewAI observability

The tracer SHALL record `crewai.mode` (resolved mode), `crewai.tools` (attached names and call count when a crew runs), and `crewai.fallback` when the adapter degrades to the deterministic draft.

#### Scenario: Mode is visible on every unit

- GIVEN a pipeline run
- WHEN the drafter step starts
- THEN a `crewai.mode` event is logged with `off`, `draft`, or `full`

### Requirement: Cubiczan brand constraints

Drafts SHALL use the brand spelling **Cubiczan** (never CubicZan or Cubic Zan). Stored finance angles and ICP features are **examples**; the product SHALL support any outbound ICP. The code critic SHALL still treat Cubiczan as correct and SHALL NOT flag it as a misspelling of CubicZan.

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

The pipeline SHALL NOT send LinkedIn or email. When CHP lock is off, approved drafts are logged as ready for Marketing Hunter / Pipeline Scout (or `pending_review` if `HUMAN_GATE_ENABLED=true`). When CHP lock is on, Scout-ready status requires a locked evidence pack.

#### Scenario: Human-gate stub when CHP is off

- GIVEN `HUMAN_GATE_ENABLED=true` and `resolved_chp_lock_enabled` is false
- WHEN Critic accepts a draft
- THEN the unit is stored as `pending_review` rather than `approved_for_scout`

#### Scenario: CHP lock supersedes the stub

- GIVEN `CHP_LOCK_ENABLED=true` (even if `HUMAN_GATE_ENABLED=false`)
- WHEN Critic accepts a draft
- THEN the unit is not `approved_for_scout` until named lock + verified pack

### Requirement: CHP lock owns send-readiness when enabled

When `resolved_chp_lock_enabled` is true, the closed loop SHALL execute research → score → draft → critic → R0 seal → structural adversary → provisional hold. It SHALL NOT set `approved_for_scout` in that same unit. Promotion SHALL wait for a named human lock and a verified evidence pack. Score totals and Learner weight updates SHALL remain deterministic Python.

#### Scenario: Live lock hold

- GIVEN `CHP_LOCK_ENABLED=true`
- WHEN `run` or a swarm worker finishes critic
- THEN the unit is stored as `provisional`
- AND `outreach_event` metadata records the CHP phase
- AND Learner MAY still apply opt-in draft outcomes
- AND the process does not send LinkedIn or email

### Requirement: Optional draft-time learner

The closed loop MAY update the Learner immediately after a successful draft when `LEARN_ON_DRAFT` or mock simulate is enabled. Otherwise Learner updates wait for an explicit `learn` event or optional LiveKit auto transcript.

#### Scenario: Mock swarm still demonstrates learning

- GIVEN `MOCK_MODE=true` and `SIMULATE_OUTCOMES=true`
- WHEN `swarm --once` completes a batch
- THEN simulated outcomes update weights and patterns for the next batch
