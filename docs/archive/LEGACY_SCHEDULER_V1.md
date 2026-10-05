# SKOPRÆD legacy-v1 algorithm

**SKOPRÆD legacy-v1** stands for **Hierarchical Adaptive Radar Multi-objective Optimizer with Network-aware Yield**.

Its job is not simply to rank repositories by "activity". It decides which upstreams should be scanned first when API calls, CI time, network requests, or analyst attention are limited.

## Why a nested model?

A busy repository is not always important. A quiet repository may be critical because dozens of projects depend on it. A repository with little recent activity may still deserve a scan when the model is uncertain about it. A security signal should also be able to outrank ordinary development velocity.

SKOPRÆD legacy-v1 therefore evaluates every candidate through six nested layers.

## Layer 1 — robust ecosystem-local normalization

Each feature is normalized **inside its own ecosystem** instead of globally.

For feature (x):

$$
z = mathrm{clip}left(rac{x-mathrm{median}(X)}
{1.4826cdotmathrm{MAD}(X)+epsilon}, -c, cight)
$$

This makes Android, Linux, AI tooling, and other ecosystems comparable even when their raw activity distributions differ by orders of magnitude.

Median/MAD is used instead of mean/standard deviation so one extremely active repository cannot distort the whole ecosystem.

## Layer 2 — hierarchical local signal

The normalized vector is not flattened immediately.

First, SKOPRÆD legacy-v1 constructs two latent subspaces:

$$
A =
0.34z_{commit}
+0.22z_{release}
+0.16z_{issue}
+0.18z_{maintainer}
+0.10z_{novelty}
$$

$$
R =
0.42z_{security}
+0.36z_{breakage}
+0.22z_{dependency}
$$

where (A) is development activity and (R) is operational risk.

The interaction term is:

$$
I = sigma(A)sigma(R)
$$

and the final local signal is:

$$
L = sigma(0.54A + 0.46R + 0.55I)
$$

The interaction term is important: high activity and high risk together should be more interesting than either signal alone.

## Layer 3 — Bayesian change probability with temporal decay

Every repository carries a Beta prior:

$$
p sim Beta(alpha,eta)
$$

After observing successful and unsuccessful change detections:

$$
alpha' = alpha + hits
$$

$$
eta' = eta + misses
$$

The posterior mean is:

$$
E[p] = rac{alpha'}{alpha'+eta'}
$$

Freshness is then applied using an exponential half-life:

$$
d(t)=2^{-t/h}
$$

where (h) is the configured half-life.

SKOPRÆD legacy-v1 keeps a 20% long-tail prior rather than erasing old evidence completely:

$$
P_{change}=E[p](0.2+0.8d(t))
$$

Posterior variance is retained as an **uncertainty signal**, which later creates an exploration bonus.

This is the first exploration/exploitation loop.

## Layer 4 — dependency graph diffusion

Repositories form a directed dependency graph.

If:

$$
A ightarrow B
$$

then A depends on B. SKOPRÆD legacy-v1 reverses contribution flow during PageRank-style diffusion so B receives influence from its dependents.

For node (i):

$$
r_i^{(k+1)}
=
rac{1-d}{N}
+
d
left(
sum_{jightarrow i}rac{r_j^{(k)}}{out(j)}
+
rac{D^{(k)}}{N}
ight)
$$

where (D) is the dangling-node mass.

This means a quiet kernel, protocol library, compiler component, or framework can rank highly because many tracked projects transitively rely on it.

## Layer 5 — robust anomaly energy

SKOPRÆD legacy-v1 computes separate feature-group energies:

1. development activity,
2. security/breakage risk,
3. dependency/maintainer/novelty context.

For each group (G):

$$
E_G = sqrt{rac{1}{|G|}sum_{zin G}z^2}
$$

Then:

$$
A_{outlier}
=
sigma(
0.50E_{activity}
+0.30E_{risk}
+0.20E_{context}
-0.75
)
$$

This intentionally differs from the local signal. A repository can have moderate absolute utility while still being statistically unusual relative to peers.

## Layer 6 — multi-objective utility fusion

The base utility is:

$$
U =
w_L L
+w_P P_{change}
+w_G G
+w_A A_{outlier}
+w_Q Q
+w_S S
$$

where:

- (G): normalized graph influence,
- (Q): Bayesian uncertainty,
- (S): transformed security signal.

A mild information-density term adjusts the result by scan cost:

$$
U' = Uleft(1+0.08log(1+rac{1}{cost})ight)
$$

The adjustment is deliberately weak so tiny jobs do not dominate just because they are cheap.

## Layer 7 — constrained combinatorial scheduler

Simple sorting is insufficient because the utility of one candidate changes after other candidates have already been selected.

For candidate (c) and partial schedule (S):

$$
Delta U(c|S)
=
U'_c
+
B_{diversity}
+
B_{exploration}
-
P_{redundancy}
-
P_{dependency-overlap}
$$

### Diversity bonus

$$
B_{diversity}
=
rac{lambda_d}{1+n_{ecosystem}}
$$

The first candidate from an ecosystem gets a stronger bonus than its fifth.

### Redundancy penalty

$$
P_{redundancy}
=
lambda_r n_{ecosystem}
$$

This prevents a single noisy ecosystem from consuming the entire budget.

### Dependency-overlap penalty

For dependency sets (D_a) and (D_b), SKOPRÆD legacy-v1 computes Jaccard overlap:

$$
J(a,b)=rac{|D_acap D_b|}{|D_acup D_b|}
$$

The maximum overlap with already selected candidates becomes a penalty.

This discourages spending multiple expensive scans on repositories likely to reveal nearly the same upstream dependency information.

## Search strategy

The final optimization resembles a constrained knapsack problem with state-dependent utility.

Exact exhaustive search grows exponentially, so SKOPRÆD legacy-v1 uses a bounded **beam search**:

1. order candidates by a mixture of absolute utility and utility density;
2. branch each state into "skip" and "include";
3. reject states violating budget or ecosystem ceilings;
4. calculate state-dependent marginal utility;
5. deduplicate equivalent states;
6. keep only the best (B) states;
7. enforce ecosystem minimums at the end.

With N repositories, beam width B, and average dependency-set operation cost D, the current implementation has a conservative worst-case scheduling bound of roughly:

$
O(NB(ND + log B))
$

The ND term comes from comparing a candidate's dependency set with repositories already selected in each beam state; the log B term comes from bounded state ordering. In ordinary runs the selected sets are much smaller than N, so observed cost is substantially lower. The bounded beam width keeps runtime predictable enough for CI scheduling while preserving significantly more search quality than greedy ranking.

## What this teaches

SKOPRÆD legacy-v1 intentionally combines ideas normally studied separately:

- robust statistics,
- Bayesian inference,
- exponential time decay,
- graph centrality,
- anomaly detection,
- multi-objective optimization,
- exploration vs. exploitation,
- submodular-style diversity shaping,
- constrained combinatorial search,
- deterministic engineering and reproducibility.

The point is not to be complicated for its own sake. Every layer corresponds to a failure mode of a simpler upstream watcher.

## Future extensions

Useful research directions include:

- Thompson sampling instead of a deterministic uncertainty bonus;
- online weight adaptation from scan reward;
- community detection before scheduling;
- transitive dependency-risk propagation;
- incremental PageRank;
- Pareto-front beam pruning;
- learned scan-cost prediction;
- change-point detection on commit/release arrival processes;
- hierarchical priors shared across ecosystems.
