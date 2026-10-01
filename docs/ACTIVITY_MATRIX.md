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


## Activity Matrix v2 — Engineering Health

Activity Matrix v2 adds measured engineering-health surfaces without duplicating
the existing impact Issue, Wiki, Release, Milestone, review, fork, or CI flows.

### Deterministic HARMONY benchmark

The daily health pass builds a deterministic synthetic portfolio and records:

- median / minimum / maximum scheduler runtime;
- selected candidate count and total budget cost;
- total utility, portfolio coverage, and content score;
- a SHA-256 hash of the selected portfolio;
- whether repeated runs produced the exact same selection.

A rolling baseline is maintained separately for GitHub and GitLab. Runtime
regression is triggered only when the measured median exceeds the configured
baseline ratio. A selection-hash mismatch across repeated identical runs is
treated as a determinism regression.

### Repository security posture

The cross-platform posture audit checks real repository automation for:

- GitHub pull_request_target trust-boundary usage;
- write-all GitHub workflow permissions;
- missing explicit GitHub workflow permissions;
- download-and-pipe-to-shell patterns in GitHub Actions or .gitlab-ci.yml;
- credential-like values in production source/configuration.

Tests, documentation, telemetry data, and generated reports are excluded from
the production secret-pattern sweep.

### Incident lifecycle

Benchmark and security regressions use a fingerprinted state machine:

1. first active evidence creates one incident Issue;
2. unchanged evidence creates no new comment;
3. changed evidence can update the Issue after the cooldown;
4. recovery adds a recovery note and closes the Issue automatically;
5. a later regression can create a new lifecycle.

This keeps engineering activity proportional to real state transitions rather
than to scheduler frequency.

### Daily evidence

GitHub Engineering Health runs inside the existing Activity Matrix workflow.
The first Matrix run of a UTC day creates the daily benchmark/security/health
evidence; later runs that day exit without producing another health report.

GitLab Engineering Health runs through the GitHub-hosted GitLab Bridge. It
checks the current day's files in GitLab first and exits immediately when the
daily evidence already exists.

The daily evidence paths are:

- reports/benchmarks/
- reports/security/
- reports/health/
- state/benchmark_github.json / state/benchmark_gitlab.json
- state/engineering_health_github.json / state/engineering_health_gitlab.json

## Runtime

GitHub Activity Matrix runs every six hours on off-boundary minute 43.

GitLab Activity Matrix runs inside the existing GitHub-hosted GitLab Bridge and
is part of bridge health monitoring.

The planner and all automation entrypoints are validated on Python 3.10–3.13.

## Activity Matrix v3 — Maintenance Intelligence

Activity Matrix v3 adds repository-maintenance surfaces that are independent
from upstream-content activity and Engineering Health.

### GitHub maintenance evidence

The daily GitHub maintenance pass measures:

- recent Actions reliability across a bounded completed-run window;
- failure ratio and consecutive failed runs;
- Discovery Garden fork synchronization against the upstream repository;
- open Issue and Pull Request staleness with separate age windows;
- floating GitHub Action references such as @main, @master, or @HEAD.

Maintenance incidents use the same fingerprint/cooldown/recovery state machine
as Engineering Health. Unchanged evidence creates no new comment.

### GitLab maintenance evidence

GitLab maintenance runs through the GitHub-hosted Bridge and measures:

- stale project Issues and Merge Requests;
- stale non-default branches;
- current Release inventory;
- workflow reference posture from the mirrored repository content.

GitLab Hosted Runner history is deliberately excluded from CI reliability
scoring because hosted jobs are unavailable for this account; Bridge Health is
the authoritative execution-health signal instead.

### Incident vs report-only surfaces

The following can create a lifecycle Issue when the configured threshold is
crossed:

- CI reliability regression;
- a governed fork falling materially behind its upstream;
- enough stale open engineering work;
- floating third-party workflow action references.

Branch age and Release inventory are report-only by default. They provide real
maintenance context without manufacturing tasks when no intervention is
necessary.

### Daily evidence paths

- reports/maintenance/github-YYYY-MM-DD.json
- reports/maintenance/gitlab-YYYY-MM-DD.json
- state/maintenance_github.json
- state/maintenance_gitlab.json

Both platforms produce at most one maintenance evidence report per UTC day.


## Activity Matrix v4 — Governance

Matrix v4 adds a governance layer that audits the radar itself rather than
creating another user-facing activity surface.

### Data quality

The daily governance pass validates the repository/project model state for:

- stale observations beyond the configured freshness window;
- repeated collector error streaks;
- impossible success/failure counters;
- unbounded change or semantic-impact history windows.

The signal is ratio-aware so one temporarily stale upstream does not create an
incident in a healthy large universe.

### State growth

Every JSON state file is measured daily.

Governance records:

- total state bytes;
- largest state files;
- files that exceed the per-file budget;
- whether the aggregate state budget has been exceeded.

A growth incident is therefore backed by actual on-disk evidence instead of a
guess about repository size.

### Cross-platform parity

A small, explicit allowlist of files is required to stay byte-identical across
GitHub and GitLab. It includes shared engine, Activity Matrix, health,
maintenance, governance, configuration, documentation, and shared tests.

Platform-specific executors are intentionally excluded.

A missing or mismatched shared file activates a high-severity parity incident.
The incident is fingerprint-deduplicated, updated only when evidence changes,
and automatically closed when parity is restored.

### Daily governance evidence

GitHub writes:

- state/governance_github.json
- reports/governance/github-YYYY-MM-DD.json

GitLab writes:

- state/governance_gitlab.json
- reports/governance/gitlab-YYYY-MM-DD.json

A normal audit creates no Issue or comment. Platform actions happen only when a
governance signal changes state.

### Matrix v4 lifecycle

The resulting engineering surface now spans:

Radar observation
→ HARMONY scoring
→ impact task / knowledge / release surfaces
→ benchmark and security health
→ CI, fork, stale-work, and workflow maintenance
→ data-quality / storage / cross-platform governance
→ incident update and automatic recovery close

This keeps activity broad while still requiring every action to be supported by
measured engineering evidence.


## Activity Matrix v5 — Downstream Impact

Matrix v5 connects upstream intelligence to concrete downstream engineering
work. The objective is not to broadcast every upstream change into every
repository. Every downstream task requires an explicit source-to-target map and
a measured material change.

### Explicit impact map

The mapping lives in config/downstream_projects.json.

Examples include:

- Linux / Cilium / WireGuard → TCP_Optimiser_RS;
- Linux → susfs4ksu;
- Linux / LLVM → OnePlus13-kernel;
- mihomo / sing-box / Tailscale / WireGuard → mihomo and Bettbox;
- MCP / OpenAI Agents / Anthropic / AutoGen / LangChain → axymorrsen-infra-mcp;
- QEMU → TEESimulator.

Repositories without an explicit mapping receive no downstream task.

### Material-change gate

By default an observation must:

- have semantic impact >= 6.0; and
- touch a material field such as release, commit identity, default branch,
  archive/disable state, or license;

or exceed the critical impact threshold >= 8.0.

Popularity-only churn below the critical threshold is ignored.

### Downstream lifecycle

A new mapped material change can create one Issue in the target repository.
The task contains:

- source platform and upstream URL;
- semantic-impact score;
- changed fields;
- HARMONY reasons;
- stable evidence hash;
- repository-specific validation checklist.

If the same evidence appears again, no action is taken. New evidence may add a
comment to an open task after the update cooldown. A closed task may create a
new lifecycle only after the longer create cooldown.

### Action limits

The planner may evaluate multiple mapped projects, but platform writes remain
bounded:

- at most 2 downstream actions per run;
- at most 3 downstream actions per rolling 24 hours;
- 24-hour update cooldown;
- 7-day new-lifecycle cooldown after a closed task.

### Cross-platform sources

GitHub radar observations create tasks directly in mapped GitHub repositories.

GitLab radar observations use the GitHub-hosted Bridge as the control plane.
The source evidence remains explicitly marked as GitLab, while the actionable
task is created in the mapped GitHub downstream repository. GitLab stores its
own downstream state/report evidence for auditability.

This extends Activity Matrix from repository-local activity into a real
upstream-to-downstream engineering workflow.
