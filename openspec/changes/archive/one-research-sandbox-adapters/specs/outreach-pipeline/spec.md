# Outreach Pipeline Specification

## Purpose

Run a Cubiczan-branded CrewAI crew (or a deterministic mock of the same stages) that researches a lead, scores ICP fit, drafts LinkedIn/email follow-up, self-critiques, and holds send for Pipeline Scout.

## ADDED Requirements

### Requirement: Live web refresh may use One You

When One You is the effective research provider, Researcher SHALL call You.com Search and/or Research through One `you` actions instead of the direct `YDC_API_KEY` HTTP client. Retry-once-then-cache failover is unchanged.

#### Scenario: Live web refresh via One

- GIVEN One auth, `ONE_YOU_CONNECTION_KEY`, `MOCK_MODE=false`, and `RESEARCH_PROVIDER=auto`
- WHEN a lead is processed
- THEN Researcher SHALL execute One `you` Search/Research before Drafter runs
- AND if that call fails twice, Researcher SHALL degrade to cached context and log `tool_failures`
