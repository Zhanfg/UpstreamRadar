# Discovery Garden

Discovery Garden turns UpstreamRadar from a monitor of already-known upstreams
into a continuous technology-discovery system.

Its job is to answer:

1. What new repositories are appearing across GitHub and GitLab?
2. Which of them match our engineering directions?
3. Which candidates are active, maintained, reusable, and worth studying?
4. Which candidates are strong enough to enter a governed fork queue?
5. Where should those forks live so the account does not become an unstructured
   repository dump?

## Two discovery lanes

### Global census

GitHub is scanned with the public-repository cursor:

GET /repositories?since=<repository-id>

The cursor advances monotonically and is persisted in
state/discovery_github.json.

GitLab is scanned with ordered project IDs and id_after. Its cursor is persisted
in state/discovery_gitlab.json.

A normal run therefore advances a bounded slice of the global repository
universe instead of restarting from the beginning.

### Priority search

A census of the entire public universe takes time. Every run also rotates
through direction-specific searches so relevant new work can be discovered
before the global cursor reaches it.

Current direction taxonomy:

- android-kernel
- networking
- ai-agents
- security-sandbox
- developer-tooling

The taxonomy is data, not code, and lives in config/discovery.json.

## Candidate scoring

A repository is scored from:

- direction relevance;
- recent upstream activity;
- community signal;
- ecosystem/fork signal;
- description quality;
- repository novelty;
- known open-source license metadata.

Lists, tutorials, archived repositories, and existing forks are excluded or
down-weighted.

The retained candidate set is deliberately bounded. Discovery Garden is not a
database mirror; it is an opportunity index.

## Evidence artifacts

GitHub produces:

- state/discovery_github.json
- discovery/github_candidates.json
- discovery/github_fork_queue.json
- reports/discovery/github.md

GitLab produces equivalent GitLab-specific files.

These records make discovery decisions auditable and allow later SKOPRÆD
versions to learn whether a candidate actually became useful.

## Governed fork queue

High-scoring repositories may enter a Fork Queue, but discovery and fork
execution are separate stages.

Current fork policy includes:

- minimum relevance/quality threshold;
- recent activity requirement;
- known-license preference;
- deduplication against fork history;
- maximum one new fork per platform per day;
- maximum five new forks per platform per rolling week.

This prevents repository spam and makes every fork an intentional retained
asset.

## Organization / namespace gate

Fork execution requires an explicit destination namespace.

Current configured destinations are:

- github_organization: yuezhou-build
- gitlab_namespace_path: axymorrsen-labs
- personal_fallback: false

GitLab fork execution is enabled against the public axymorrsen-labs group.

GitHub fork execution is organization-routed but remains credential-gated:
the executor requires a dedicated UPSTREAMRADAR_FORK_PAT and does not fall back
to the normal radar token. If that secret is absent or lacks fork permissions,
the executor emits SKIP/ERROR without changing the organization.

This preserves organization structure while keeping discovery scans independent
from fork write permissions.

## Logical collections

Candidates and future forks are classified into logical collections:

- android-kernel
- networking
- ai-agents
- security-sandbox
- developer-tooling

GitLab fork descriptions include the collection identifier. GitHub fork history
also records it, and organization-level topics/metadata can be applied later.

## Runtime

GitHub Discovery Garden runs every two hours at minute 17.

GitLab discovery runs through the GitHub-hosted GitLab Bridge because the GitLab
account cannot use GitLab.com hosted runners.

The bridge health state includes discovery and fork-governor outcomes, so a
broken discovery stage participates in the same deduplicated incident/recovery
loop as radar and review automation.

## Design principle

The goal is not to maximize the number of forks.

The goal is to turn the public repository universe into a continuously updated,
organized set of directions worth studying, and to retain only the strongest
projects as forked engineering assets.
