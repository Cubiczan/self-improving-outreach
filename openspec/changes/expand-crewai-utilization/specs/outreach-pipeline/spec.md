# Outreach Pipeline Specification

## Purpose

Run Self Improving Outreach — a Cubiczan-branded closed loop for **any outbound sales**. CrewAI MAY draft prose inside each swarm worker. Deterministic Python owns ICP Score math, Learner updates, the code brand critic, and send-hold for Pipeline Scout.

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Cubiczan brand constraints

Drafts SHALL use the brand spelling **Cubiczan** (never CubicZan or Cubic Zan). Stored finance angles and ICP features are **examples**; the product SHALL support any outbound ICP. The code critic SHALL still treat Cubiczan as correct and SHALL NOT flag it as a misspelling of CubicZan.

#### Scenario: Critic accepts correct Cubiczan spelling

- GIVEN a draft whose body contains "Cubiczan" and does not contain "CubicZan" or "Cubic Zan"
- WHEN Critic runs
- THEN it SHALL NOT report "brand misspelling"
- AND the draft may be accepted if no other issues apply
