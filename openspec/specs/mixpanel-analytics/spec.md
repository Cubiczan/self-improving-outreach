# Mixpanel Analytics Specification

## Purpose

Send Cubiczan self-improving-outreach (SIO) product analytics to Mixpanel from the Python server using env-based project tokens. Analytics MUST NOT send LinkedIn, invent signup, or block the pipeline.

## Requirements

### Requirement: Env-based Mixpanel tokens

The system SHALL read Mixpanel project tokens from the environment. When `ENVIRONMENT` is `prod` or `production`, the token SHALL be `MIXPANEL_TOKEN_PROD` or `MIXPANEL_TOKEN`. Otherwise the token SHALL be `MIXPANEL_TOKEN` or `MIXPANEL_TOKEN_DEV`. Tokens SHALL NOT be hardcoded in Python as the only resolution path. A missing token SHALL disable tracking (no-op). `show-config` SHALL report `mixpanel_configured` and resolved `environment` and SHALL NOT print token values.

#### Scenario: Production token wins on production

- GIVEN `ENVIRONMENT=production` and `MIXPANEL_TOKEN_PROD` set
- WHEN Settings resolve
- THEN `resolved_mixpanel_token` is the prod token
- AND `resolved_environment` is `production`

#### Scenario: Dev token is the default

- GIVEN `ENVIRONMENT` unset or `development` and `MIXPANEL_TOKEN_DEV` set
- WHEN Settings resolve
- THEN `resolved_mixpanel_token` is the dev token
- AND `resolved_environment` is `development`

#### Scenario: Missing token is a no-op

- GIVEN no Mixpanel token env vars
- WHEN `track_linkedin_connect_accepted` is called
- THEN no network request is made
- AND the caller does not raise

### Requirement: Super properties on every event

Every tracked event SHALL include super properties `product=sio`, `platform=server`, and `environment=production|development`.

#### Scenario: Super properties are merged

- GIVEN a configured Mixpanel client in development
- WHEN `sign_up_completed` is tracked
- THEN the payload includes `product=sio`, `platform=server`, and `environment=development`

### Requirement: Identity is a stable operator pk

The system SHALL `identify(user_id)` only with a stable operator / user id (DB pk or `OPERATOR_ID` / `MIXPANEL_DISTINCT_ID`). Email-shaped ids SHALL be refused. `people.set` SHALL run only after identify and SHALL set minimal profile attrs. `reset()` SHALL clear in-process identity. This repo has no logout route; `analytics reset` is the hook.

#### Scenario: Identify rejects email

- GIVEN a Mixpanel client
- WHEN `identify("sam@cubiczan.com")` is called
- THEN distinct_id is not set to that email
- AND `people.set` is not sent

#### Scenario: Operator env identifies without signup

- GIVEN `OPERATOR_ID=42` and a Mixpanel token
- WHEN the analytics client is constructed
- THEN the client is identified as `42`
- AND `sign_up_completed` is not fired by construction alone

### Requirement: sign_up_completed is opt-in

`sign_up_completed` SHALL fire only from the public helper or `analytics sign-up` CLI, with properties `sign_up_method`, `platform`, and optional `referral_source`. The Python product SHALL NOT invent an account-creation flow.

#### Scenario: CLI sign-up hook

- GIVEN a Mixpanel token and `--user-id 99 --method cli`
- WHEN `analytics sign-up` runs
- THEN `sign_up_completed` is tracked with `sign_up_method=cli`
- AND the client is identified as `99`

### Requirement: linkedin_connect_accepted is the value moment

`track_linkedin_connect_accepted(company, person_name, linkedin_url, batch_id=None)` SHALL be public. `apply_learn_event` SHALL call it when a LearnEvent is a LinkedIn accept (explicit `linkedin_connect_accepted`, notes containing that signal, or equivalent). Properties SHALL include `company`, `person_name`, `linkedin_url`, and optional `batch_id`. Simulated draft outcomes SHALL NOT fire it unless the LearnEvent is marked. This SHALL NOT send LinkedIn.

#### Scenario: Learner live accept fires the value moment

- GIVEN a lead and `LearnEvent(linkedin_connect_accepted=True)`
- WHEN `apply_learn_event` runs
- THEN `linkedin_connect_accepted` is tracked with the lead company and contact name

#### Scenario: Ordinary meeting does not fire it

- GIVEN a LearnEvent with `outcome=meeting` and no accept flag
- WHEN `apply_learn_event` runs
- THEN `linkedin_connect_accepted` is not tracked

### Requirement: contact_submitted is site-only

The Python product SHALL NOT implement `contact_submitted`. That event belongs to the Cubiczan site.

#### Scenario: Server module does not expose contact_submitted

- GIVEN the SIO analytics module
- WHEN callers inspect public event names
- THEN `contact_submitted` is documented as site-only and is not tracked by this package
