# Design

## Boundless as OpenAI-compatible LLM

Two Boundless products share the `BOUNDLESS_API_KEY` name:

| Product | Base URL | Typical model |
| --- | --- | --- |
| BoundlessAPI catalog (default) | `https://api.boundlessapi.com/v1` | `gpt-4o-mini` (override to a live catalog ID such as `gpt-5.4-mini`) |
| boundless.network inference (Sam's credit) | `https://api.inference.boundless.network/v1` | `glm-5.2` |

Default `BOUNDLESS_BASE_URL` is BoundlessAPI. README tells Sam to override if the dashboard shows the network inference URL.

`LLM_PROVIDER=openai|boundless` (default openai). When `boundless`, CrewAI `LLM` is built with `custom_openai=True`, `base_url`, and the Boundless key. The same key/base are copied into `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_API_BASE` so LiteLLM picks them up. When `openai` is requested but only a Boundless key exists, Boundless is the fallback.

`Settings.use_crewai` is true when not mock and an effective LLM key exists (OpenAI or Boundless). `MOCK_MODE=true` still forces the deterministic crew.

## Voice learner

`parse_voice_transcript` accepts JSON with `positive` / `sentiment` / `outcome` / `thumbs`, plus `notes` and `pattern_id`. CLI `voice --transcript-file` uses that. After a successful pipeline draft, `LIVEKIT_FEEDBACK_AUTO=true` reads `LIVEKIT_TRANSCRIPT_PATH` (file or `{lead_id}.json` directory) and calls `record_voice_feedback`.

`record_voice_feedback` always logs an `outreach_event` with `channel=voice` and `metadata.source=livekit`. LiveKit SDK keys remain optional; mock interview + file ingest work without them.
