# SKOPRÆD legacy-v2 — Content-Aware Multi-Timescale Scheduling

SKOPRÆD legacy-v2 extends the original scheduler from a single-observation ranking
system into a stateful information-selection engine.

The design goal is not complexity for its own sake. Every new layer must answer
one of two questions:

1. **Should this upstream be observed now?**
2. **If it is observed, is the result likely to produce useful explanatory content?**

## 1. Inputs

The original scalar telemetry remains supported:

- commit / release / issue velocity;
- security and breakage signals;
- dependency importance;
- maintainer activity;
- novelty;
- Bayesian hit / miss evidence;
- scan cost and freshness.

v2 adds optional stateful telemetry:

- binary change history;
- semantic-impact history;
- observation count;
- source reliability;
- failure streak;
- content signal.

Existing v1 callers remain source-compatible because all new fields are
optional and appended to the signal schema.

## 2. Hierarchical robust normalization with shrinkage

Ecosystem-local normalization is still based on median/MAD, but tiny ecosystems
no longer trust their own scale completely.

For a local ecosystem of size n:

lambda = min(1, n / 4)

and local center/scale are shrunk toward global robust statistics:

mu = lambda * mu_local + (1-lambda) * mu_global

s = lambda * s_local + (1-lambda) * s_global

This prevents one- or two-repository ecosystems from producing unstable
extreme z-scores.

## 3. Multi-timescale dynamics

For impact history x_t, SKOPRÆD legacy-v1 maintains three EWMAs: fast, medium and slow.

Acceleration is:

a = (E_fast - E_medium) + 0.6 * (E_medium - E_slow)

and is transformed to a bounded momentum score.

This distinguishes persistently active upstreams, newly accelerating upstreams,
and upstreams that were active but are cooling down.

## 4. Online regime-shift detector

A Page-Hinkley / one-sided CUSUM style detector is applied to the normalized
impact stream.

For each observation:

C_t = C_(t-1) + x_t - mean_t - delta

The maximum excursion above the historical minimum is transformed into a
bounded change-point score.

This is intentionally lightweight and dependency-free. It is not presented as
a full Bayesian online change-point detector; it is an auditable streaming
regime-shift heuristic.

## 5. Entropy and volatility

Binary change history contributes normalized Shannon entropy.

Impact history also contributes volatility.

High entropy means the source is difficult to predict; high volatility means
the magnitude of change is unstable. Both increase the information value of a
fresh observation.

## 6. Semantic impact

Collectors no longer treat every snapshot difference equally.

Examples of high-impact transitions:

- release/tag changes;
- default-branch changes;
- archived/disabled state changes;
- new upstream commits;
- major activity-time changes.

Low-impact transitions such as a one-star increase receive much smaller
weights.

Each successful observation stores change_window, impact_window, ewma_impact,
and last_semantic_impact.

Bootstrap observations receive zero semantic impact so initial population does
not masquerade as a regime shift.

## 7. Content yield

The content-yield score combines normalized semantic impact, change-point
evidence, entropy, volatility, and momentum.

It answers:

> If this source changes now, how likely is the change to support a useful,
> evidence-rich report item rather than a low-information snapshot update?

This score is part of both candidate utility and the final content plan.

## 8. Reliability-aware scoring

Sources with repeated collection failures are discounted.

Reliability combines historical successful checks with an exponential failure
streak penalty, with a floor so a temporarily broken source is not permanently
starved.

This separates an interesting source from a currently trustworthy observation
channel.

## 9. Uncertainty-aware exploration

Bayesian posterior uncertainty is scaled by an observation-count term similar
to an upper-confidence-bound exploration pressure.

Frequently observed sources therefore receive less exploration pressure than
poorly observed sources with similar posterior uncertainty.

This creates a deterministic exploration/exploitation loop without injecting
randomness into tests or reports.

## 10. Signal-seeded graph diffusion

v1 used uniform PageRank-style diffusion.

v2 seeds graph teleport probability using local activity, content yield,
regime-shift evidence, security signal, and change probability.

The graph contains explicit dependency edges plus weak same-ecosystem affinity
edges.

A dependency hub therefore becomes important not only because of topology, but
because active high-signal dependents are currently pointing toward it.

## 11. Portfolio coverage

Selection is no longer only a sum of independent candidate values.

SKOPRÆD legacy-v1 constructs pairwise similarity from ecosystem identity, dependency-set
Jaccard similarity, and similarity of content / change-point / security
profiles.

A facility-location-style marginal coverage term rewards a candidate when it
covers parts of the tracked universe not already represented in the selected
set.

This improves content breadth: the final report is less likely to be ten near-
duplicate items from one ecosystem.

## 12. Budgeted search

The beam search now uses a state-specific fractional-knapsack upper bound.

For each partial state, remaining budget is filled optimistically by candidate
gain density. Unlike the old constant optimistic tail, the bound changes with
the state's remaining capacity.

This improves beam ordering while keeping the implementation deterministic and
inspectable.

## 13. Explainability

Every scored candidate exposes momentum, change-point score, entropy, content
yield, reliability, exploration pressure, graph influence, security focus,
final utility, and short reason tags.

Example reason tags include:

- regime-shift
- accelerating
- high-content-yield
- dependency-hub
- security-focus
- uncertainty-exploration
- likely-change
- anomalous

## 14. Content planner

The build_content_plan() function converts candidate scores into evidence-first
investigation opportunities.

It deliberately does not write articles. It emits priority, report angle,
reason tags, and strongest numeric evidence.

This keeps generated reports grounded in scheduler evidence and makes the
algorithmic complexity directly useful to repository content.

## 15. New schedule-level metrics

A ScheduleResult now includes coverage_score and content_score.

These metrics let the system observe not only whether a schedule fits the
budget, but whether the selected portfolio is broad and information-rich.

## 16. Design invariants

SKOPRÆD legacy-v2 keeps these constraints:

- no runtime third-party dependencies;
- deterministic results for deterministic inputs;
- old RepositorySignal construction remains valid;
- old pagerank_damping / pagerank_steps configuration names remain valid;
- no fabricated observations;
- no synthetic historical backfill;
- bootstrap snapshots are not counted as semantic change;
- content recommendations remain evidence-first.
