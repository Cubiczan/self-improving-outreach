# LLM Provider Specification

## Purpose

Let live CrewAI drafts call an OpenAI-compatible endpoint. Default is OpenAI. Boundless is first-class so Cubiczan can spend boundless.network inference credits (https://inference.boundless.network/) without rewriting crews.

## Requirements

### Requirement: Provider selection

The system SHALL read `LLM_PROVIDER=boundless|openai` (default `openai`). When the provider is `boundless`, CrewAI/LiteLLM SHALL use `BOUNDLESS_API_KEY` and `BOUNDLESS_BASE_URL` (`https://api.inference.boundless.network/v1`) with `Authorization: Bearer`. When the provider is `openai` and `OPENAI_API_KEY` is missing but `BOUNDLESS_API_KEY` is set, the system SHALL fall back to Boundless. Do not use `api.boundlessapi.com`.

#### Scenario: Explicit Boundless provider

- GIVEN `LLM_PROVIDER=boundless` and `BOUNDLESS_API_KEY` and `MOCK_MODE=false`
- WHEN Settings are loaded
- THEN `use_crewai` is true
- AND `llm_base_url` is `BOUNDLESS_BASE_URL` (default `https://api.inference.boundless.network/v1`)
- AND `llm_api_key` is the Boundless key, not a raw secret printed by `show-config`

#### Scenario: OpenAI falls back to Boundless

- GIVEN `LLM_PROVIDER=openai`, no `OPENAI_API_KEY`, and `BOUNDLESS_API_KEY` set
- WHEN Settings resolve the effective provider
- THEN the effective provider is `boundless`

#### Scenario: Mock mode ignores LLM keys

- GIVEN `MOCK_MODE=true` and a Boundless or OpenAI key
- WHEN a lead is drafted
- THEN the deterministic mock crew runs and no provider secret is required
- AND `resolved_crewai_mode` is `off` even if `CREWAI_MODE=full`

### Requirement: CrewAI utilization mode

The system SHALL read `CREWAI_MODE=off|draft|full`. Unset means `full` when `use_crewai` is true, otherwise `off`. `show-config` SHALL print the resolved mode, not secrets.

#### Scenario: Default full when live

- GIVEN `MOCK_MODE=false` and `OPENAI_API_KEY` or `BOUNDLESS_API_KEY`
- WHEN Settings resolve
- THEN `resolved_crewai_mode` is `full`

### Requirement: OpenAI-compatible runtime env

When the effective provider is Boundless, the adapter SHALL configure CrewAI `LLM` with `base_url` + Boundless key and SHALL set `OPENAI_API_KEY` plus `OPENAI_BASE_URL`/`OPENAI_API_BASE` so LiteLLM OpenAI clients hit Boundless.

#### Scenario: Boundless model id

- GIVEN `BOUNDLESS_MODEL` unset
- THEN the default CrewAI model is `glm-5.2`
- AND operators MAY override to other catalog ids (`dsv4`, `qwen3.6`, `nemotron3-super`, `kimi-k3`)

### Requirement: Secret-free config display

`show-config` SHALL print provider name, model, base URL, and booleans only. It SHALL NOT print API keys or secrets.

#### Scenario: Keys present

- GIVEN `BOUNDLESS_API_KEY` and `OPENAI_API_KEY` are set
- WHEN `show-config` runs
- THEN the output contains `boundless_configured` / `openai_configured` booleans
- AND the key material does not appear
