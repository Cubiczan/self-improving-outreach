# Learning Loop Specification

## ADDED Requirements

### Requirement: Mixpanel value moment on LinkedIn accept

`apply_learn_event` SHALL call `track_linkedin_connect_accepted` when the LearnEvent is marked as a LinkedIn accept (`linkedin_connect_accepted` or notes). Ordinary `meeting` / `replied` / simulated draft outcomes SHALL NOT fire it. Analytics failure SHALL NOT change Learner weights. See `mixpanel-analytics`.

#### Scenario: Scout accept flag fires Mixpanel

- GIVEN a lead and `linkedin_connect_accepted=true` on the LearnEvent
- WHEN `learn --event` runs
- THEN Mixpanel `linkedin_connect_accepted` is attempted
- AND ICP / pattern updates still apply if Mixpanel is unset
