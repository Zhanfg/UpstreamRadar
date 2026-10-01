# Activity Fabric

Activity Fabric turns UpstreamRadar telemetry into a broader engineering
lifecycle without manufacturing empty activity.

The system is event-driven. A platform action must be backed by a real change,
a measured regression, a health-state transition, or a completed reporting
cycle.

## Activity surfaces

| Surface | Trigger | Platform effect |
| --- | --- | --- |
| Signal triage | Material semantic impact | Issue / work item |
| Signal follow-up | Evidence hash changes | Issue comment / note |
| Recovery | Signal remains below threshold | Automatic close with recovery note |
| Scheduler reliability | Catch-up pressure + delayed wake | Reliability issue lifecycle |
| Code review | Real PR/MR diff | Automated heuristic review |
| Discovery | High-confidence external project | Candidate registry / governed fork |
| Fork retention | Queue + namespace + license + quota | Organization fork + history |
| Benchmark | Daily deterministic HARMONY run | Benchmark evidence report |
| Performance regression | Measured slowdown / determinism break | Regression issue lifecycle |
| Security posture | Workflow/secret posture audit | Security evidence report |
| Security regression | Critical/high finding | Security issue lifecycle |
| Weekly telemetry release | Real weekly observation threshold | Release + tag |
| Engineering cycle | First issue in weekly cycle | Milestone |
| Incident recovery | Previously degraded automation returns healthy | Note + close |
| Documentation | Architecture or policy changes | Docs / knowledge artifacts |

## Signal issues

A normal popularity fluctuation is not enough to create a task.

By default a signal must:

- have semantic impact >= 6.5; and
- either touch an important field such as release, commit identity, default
  branch, archive/disable state, or license;
- or reach the critical impact threshold >= 8.0.

Only the highest-priority signals are admitted per run, and daily creation and
update caps apply.

## Evidence updates

Every planned signal has a stable evidence hash.

If an open issue already represents the signal:

- unchanged evidence produces no platform action;
- changed evidence may add a comment/note after the cooldown;
- a recovered signal closes automatically after the recovery window;
- a materially changed signal can reopen a closed investigation.

This creates an auditable lifecycle instead of duplicate issues.

## Weekly releases and tags

A Radar Release is not created merely because a week number changed.

The default weekly threshold requires:

- at least 50 changed upstream observations; and
- at least 3 real collector runs.

The release notes summarize scan volume, changes, errors, and material signals.
The tag is deterministic, for example:

    radar-2026-W40

Only one release exists for a cycle.

## Milestones

The first qualifying issue in a cycle creates a weekly engineering milestone,
for example:

    Radar Cycle 2026-W40

Subsequent Activity Fabric issues are attached to the same cycle where the
platform supports milestones.

## Engineering Health

Engineering Health runs independently from the main upstream collector.

It contains two evidence producers:

### HARMONY benchmark

A deterministic synthetic portfolio is scheduled repeatedly and records:

- median/min/max runtime;
- selection hash;
- total cost and utility;
- coverage score;
- content score;
- determinism.

A regression issue is opened only if runtime exceeds the configured baseline
ratio or deterministic selection breaks.

### Security posture

The posture audit checks repository automation for concrete risks including:

- pull_request_target trust-boundary usage;
- write-all workflow permissions;
- implicit workflow permissions;
- download-and-pipe-to-shell patterns;
- credential-like values in production source/config.

Reports are produced daily. High/critical findings enter a real issue lifecycle.

## GitHub

GitHub Activity Fabric runs after a successful radar push and may create:

- issues;
- evidence comments;
- recovery closes;
- weekly milestones;
- weekly releases/tags.

A separate Engineering Health workflow runs once daily and persists benchmark
and security evidence.

## GitLab

GitLab Activity Fabric is executed by the GitHub-hosted GitLab Bridge because
GitLab.com hosted runners are unavailable for this account.

The Bridge additionally runs GitLab Engineering Health. That script checks for
the current day's published health evidence and exits immediately when the day
has already been processed, so the 15-minute bridge cadence does not create
15-minute health commits.

## Anti-noise invariants

Activity Fabric MUST NOT:

- create no-op commits;
- create duplicate issues for the same signal;
- comment when evidence is unchanged;
- create releases for empty periods;
- create arbitrary tags solely for profile activity;
- manufacture reviews without a real diff;
- create forks outside the governed queue;
- backdate or fabricate observations.

Activity is a consequence of engineering state, not the optimization target.
