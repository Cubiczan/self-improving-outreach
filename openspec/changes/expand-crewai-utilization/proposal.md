# Proposal: Expand CrewAI utilization inside swarm workers

## Why

CrewAI currently runs a sequential Researcher → Scorer → Drafter → Critic crew that only replaces draft **body**. `build_you_tool` exists but is not attached. Agents are framed as CFO/CIO-only Cubiczan finance copy even though the product is **Self Improving Outreach** for any outbound sales. CrewAI should do more useful work *inside* each swarm worker without becoming the whole system.

## What

- `CREWAI_MODE=off|draft|full` (default `full` when `use_crewai`, else `off`)
- `draft` keeps the current 4-agent body-only crew (compat)
- `full` attaches You.com (and read-only pattern/weight) tools, adds Strategist + Adversary Critic
- General outbound agent goals/backstories; stored patterns/weights stay examples
- Tracer events for `crewai.mode`, tool attach/call counts, and fallback
- Code brand critic, ICP Score math, and Learner remain deterministic
- CrewAI Strategist / Adversary Critic / tools stay complementary to the CHP decision lock (R0 / structural adversary / named human lock / evidence pack / scout gate)
- Optional soft import of external `consensus-hardening-protocol` for a prompt floor — no hard dependency, does not replace the in-repo CHP lock

## Scope

In: Settings, CrewAI adapter, pipeline wiring, You.com mid-crew refresh helper, tests, README, OpenSpec.

Out: Making CrewAI recompute ICP scores or Learner weights, auto-send, bypassing CHP send-readiness, requiring the external CHP package, changing the mock/no-keys CI path.
