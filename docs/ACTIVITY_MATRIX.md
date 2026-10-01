# Activity Matrix

Activity Matrix expands UpstreamRadar from a commit-heavy telemetry pipeline into
a multi-surface engineering activity system.

The objective is not to manufacture profile activity. Every action must be
triggered by real repository evidence and must remain auditable.

## Supported activity surfaces

GitHub:
- evidence-backed impact Issues;
- follow-up Issue comments;
- benchmark reports committed to the repository;
- durable Wiki intelligence pages;
- weekly intelligence Releases and Tags;
- monthly intelligence Milestones;
- Pull Request review through the existing reviewer;
- Discovery Garden forks;
- CI runs and workflow artifacts.

GitLab:
- evidence-backed Issues and notes;
- benchmark reports committed to the project;
- native Wiki pages;
- Releases and repository Tags;
- Milestones;
- Merge Request review and inline DiffNotes;
- Discovery Garden forks;
- Bridge health incidents and recovery notes.

## Evidence model

The planner consumes the latest real Radar run rather than inventing a second
metric system.

Inputs include:
- changed upstream count;
- collection errors;
- HARMONY portfolio coverage;
- content score;
- top semantic-impact transition;
- HARMONY reason tags such as regime-shift and security-focus;
- current Discovery Garden fork queue size.

## Strong-signal rule

Issues and Releases require more than normal popularity churn.

They are eligible when either:
- semantic impact exceeds the configured threshold; or
- HARMONY identifies a strong regime-shift/security signal.

This prevents stars/forks/watchers noise from turning into fake engineering
work.

## Budgets and cooldowns

Each surface has its own daily budget and cooldown.

Default policy:
- impact Issues: at most 2/day, 72-hour per-source cooldown;
- benchmark snapshots: at most 2/day, 12-hour cooldown;
- Wiki page: at most 1/day;
- intelligence Release: at most 1/day and 7-day cooldown;
- Milestone: at most 1/day, with a unique monthly key;
- Issue notes: limited independently.

A rerun therefore updates or reuses existing objects instead of opening
duplicates.

## Platform identity

Automated commits use explicit bot identities where the platform supports it.
Issues, Releases, Wiki pages and Milestones state that they were generated from
UpstreamRadar evidence.

Automation must not impersonate manual human activity.

## Lifecycle

A high-value upstream event can now produce a real engineering lifecycle:

Radar observation
→ semantic-impact / HARMONY evidence
→ impact Issue
→ monthly Milestone
→ benchmark snapshot
→ Wiki intelligence page
→ Release/Tag when the weekly threshold is satisfied
→ code review / downstream follow-up
→ incident recovery or Issue update

This creates diversity because the engineering event genuinely has multiple
useful representations, not because one event is artificially split into
meaningless commits.

## Runtime

GitHub Activity Matrix runs every six hours on off-boundary minute 43.

GitLab Activity Matrix runs inside the existing GitHub-hosted GitLab Bridge and
is part of bridge health monitoring.

The planner and all automation entrypoints are validated on Python 3.10–3.13.
