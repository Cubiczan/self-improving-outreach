# Design

## Modes

`CREWAI_MODE` is `off`, `draft`, or `full`. Empty / unset means auto:

- Mock mode or missing LLM credentials → `off` (CI unchanged)
- Otherwise `full` when `use_crewai` else `off`

`draft` is the compatibility crew: Researcher, Interpreter Scorer, Drafter, Critic. No tools. Body-only replacement of the deterministic template.

`full` is sequential:

1. Researcher — You.com tool; general company/contact brief
2. Interpreter Scorer — explains the deterministic score; does not invent weights
3. Strategist — picks/justifies a scored `message_patterns` angle (optional You.com + memory-read tools)
4. Drafter — channel-appropriate outbound note
5. Adversary Critic — draft-brain attack on weak claims, compliance/send risk, overclaims; returns hardened body. Notes MAY be extras on the CHP structural adversary report.

The pipeline still runs the code brand critic after CrewAI. Score and Learner stay in Python. The in-repo CHP decision lock (R0 → structural adversary → named human lock → evidence pack) remains authoritative for send-readiness. CrewAI MUST NOT skip or replace that lock.

## Tools

`build_you_tool` wraps `ResilientYouCom.refresh_query` so mid-crew search retries once then degrades to cache. `build_memory_tool` is read-only (`patterns` / `weights`) and does not write Learner state.

Tool call counts are incremented in `_run` and emitted as `crewai.tools` (`attached`, `calls`, `names`). Failures emit `crewai.fallback`.

## CHP

The Cubiczan CHP decision lock in this repo is the send-readiness path. CrewAI's Adversary Critic is complementary draft-brain only.

Adversary prompts MAY mention governance hardening. If the optional external `consensus-hardening-protocol` package imports cleanly, the adapter MAY mention a resolved general-domain floor. That import is unrelated to `self_improving_outreach.chp` and is not a dependency. Missing package is not an error.
