#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace upstreamradar::museum {

inline double clamp01(double value) {
    if (!std::isfinite(value)) return 0.0;
    return std::clamp(value, 0.0, 1.0);
}

inline double stable_sigmoid(double value) {
    if (value >= 0.0) {
        const double z = std::exp(-value);
        return 1.0 / (1.0 + z);
    }
    const double z = std::exp(value);
    return z / (1.0 + z);
}

struct RepositorySignal {
    std::string name;
    std::string ecosystem;
    std::uint32_t cost{1};
    double freshness_hours{0.0};

    double commit_velocity{0.0};
    double release_velocity{0.0};
    double issue_velocity{0.0};
    double contributor_velocity{0.0};
    double maintainer_activity{0.0};

    double security_signal{0.0};
    double breakage_risk{0.0};
    double dependency_importance{0.0};
    double novelty{0.0};
    double downstream_relevance{0.0};

    std::uint32_t recent_change_hits{0};
    std::uint32_t recent_change_misses{0};
    std::uint32_t observation_count{0};
    std::uint32_t failure_streak{0};
    double source_reliability{1.0};

    std::vector<int> change_history;
    std::vector<double> impact_history;
    std::vector<std::string> dependencies;
    std::set<std::string> tags;

    [[nodiscard]] std::uint32_t effective_cost() const noexcept {
        return std::max<std::uint32_t>(1, cost);
    }

    [[nodiscard]] std::uint32_t observations() const noexcept {
        return std::max(
            observation_count,
            recent_change_hits + recent_change_misses
        );
    }

    [[nodiscard]] std::vector<std::string> normalized_dependencies() const {
        std::set<std::string> unique;
        for (const auto& dependency : dependencies) {
            if (!dependency.empty() && dependency != name) {
                unique.insert(dependency);
            }
        }
        return {unique.begin(), unique.end()};
    }

    void validate() const {
        if (name.empty()) {
            throw std::invalid_argument("repository name must not be empty");
        }
    }
};

struct Vote {
    std::string exhibit;
    double score{0.0};
};

struct Gallery {
    std::string family;
    double consensus{0.0};
    double disagreement{0.0};
    std::vector<Vote> votes;

    static Gallery from_votes(
        std::string family,
        std::vector<Vote> votes
    ) {
        if (votes.empty()) {
            return {
                .family = std::move(family),
                .consensus = 0.0,
                .disagreement = 0.0,
                .votes = {},
            };
        }

        double mean = 0.0;
        for (const auto& vote : votes) {
            mean += clamp01(vote.score);
        }
        mean /= static_cast<double>(votes.size());

        double variance = 0.0;
        for (const auto& vote : votes) {
            const double delta = clamp01(vote.score) - mean;
            variance += delta * delta;
        }
        variance /= static_cast<double>(votes.size());
        const double disagreement = clamp01(std::sqrt(variance) * 2.0);
        const double consensus = clamp01(
            mean * (1.0 - 0.22 * disagreement)
        );

        for (auto& vote : votes) {
            vote.score = clamp01(vote.score);
        }

        return {
            .family = std::move(family),
            .consensus = consensus,
            .disagreement = disagreement,
            .votes = std::move(votes),
        };
    }
};

struct MuseumEvidence {
    Gallery robust;
    Gallery change;
    Gallery information;
    Gallery graph;
    Gallery exploration;
    Gallery sketches;
    double consensus{0.0};
    double disagreement{0.0};

    static MuseumEvidence combine(
        Gallery robust,
        Gallery change,
        Gallery information,
        Gallery graph,
        Gallery exploration,
        Gallery sketches
    ) {
        const std::vector<double> gallery_scores{
            robust.consensus,
            change.consensus,
            information.consensus,
            graph.consensus,
            exploration.consensus,
            sketches.consensus,
        };
        double mean = 0.0;
        for (double value : gallery_scores) mean += value;
        mean /= static_cast<double>(gallery_scores.size());

        double variance = 0.0;
        for (double value : gallery_scores) {
            const double delta = value - mean;
            variance += delta * delta;
        }
        variance /= static_cast<double>(gallery_scores.size());
        const double disagreement = clamp01(std::sqrt(variance) * 2.0);
        const double consensus = clamp01(
            mean * (1.0 - 0.24 * disagreement)
        );

        return {
            .robust = std::move(robust),
            .change = std::move(change),
            .information = std::move(information),
            .graph = std::move(graph),
            .exploration = std::move(exploration),
            .sketches = std::move(sketches),
            .consensus = consensus,
            .disagreement = disagreement,
        };
    }
};

struct Candidate {
    std::string name;
    std::string ecosystem;
    std::uint32_t cost{1};

    double change_probability{0.0};
    double uncertainty{0.0};
    double local_signal{0.0};
    double graph_influence{0.0};
    double structural_novelty{0.0};
    double tail_risk{0.0};
    double reliability{1.0};
    double exploration{0.0};
    double risk_adjusted_utility{0.0};
    double utility{0.0};

    MuseumEvidence museum;
    std::vector<std::string> reasons;
    std::set<std::string> tags;
};

struct SchedulerConfig {
    double empirical_bayes_strength{4.0};
    double empirical_bayes_shrinkage{0.35};
    double cvar_quantile{0.75};
    double tail_risk_penalty{0.11};
    double museum_weight{0.12};
    double museum_disagreement_penalty{0.08};
    std::size_t ecosystem_cap{3};
    std::size_t beam_width{128};
    double coverage_bonus{0.08};
    double redundancy_penalty{0.10};

    void validate() const {
        if (!(empirical_bayes_strength > 0.0)) {
            throw std::invalid_argument(
                "empirical_bayes_strength must be positive"
            );
        }
        if (empirical_bayes_shrinkage < 0.0 ||
            empirical_bayes_shrinkage > 1.0) {
            throw std::invalid_argument(
                "empirical_bayes_shrinkage must be in [0,1]"
            );
        }
        if (cvar_quantile < 0.5 || cvar_quantile >= 1.0) {
            throw std::invalid_argument(
                "cvar_quantile must be in [0.5,1)"
            );
        }
        if (ecosystem_cap == 0 || beam_width < 8) {
            throw std::invalid_argument(
                "ecosystem_cap must be positive and beam_width >= 8"
            );
        }
    }
};

} // namespace upstreamradar::museum
