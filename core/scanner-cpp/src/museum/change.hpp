#pragma once

#include "model.hpp"
#include "robust.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <span>
#include <vector>

namespace upstreamradar::museum::change {

struct BocpdResult {
    double reset_probability{0.0};
    double expected_run_length{0.0};
    std::vector<double> posterior;
};

inline double cusum_score(
    std::span<const double> values,
    double drift = 0.02
) {
    if (values.size() < 2) return 0.0;

    std::vector<double> xs;
    xs.reserve(values.size());
    for (double value : values) {
        xs.push_back(clamp01(value));
    }

    const double mean =
        std::accumulate(xs.begin(), xs.end(), 0.0) /
        static_cast<double>(xs.size());

    double positive = 0.0;
    double negative = 0.0;
    double maximum = 0.0;
    for (double value : xs) {
        const double residual = value - mean;
        positive = std::max(
            0.0,
            positive + residual - drift
        );
        negative = std::min(
            0.0,
            negative + residual + drift
        );
        maximum = std::max(
            maximum,
            std::max(positive, -negative)
        );
    }
    return clamp01(
        1.0 - std::exp(-2.4 * maximum)
    );
}

inline double page_hinkley_score(
    std::span<const double> values,
    double delta = 0.04,
    double scale = 1.25
) {
    if (values.size() < 2) return 0.0;

    double running_mean = 0.0;
    double cumulative = 0.0;
    double minimum = 0.0;
    double peak = 0.0;

    for (std::size_t index = 0; index < values.size(); ++index) {
        const double value = clamp01(values[index]);
        const double count =
            static_cast<double>(index + 1);

        running_mean +=
            (value - running_mean) / count;
        cumulative +=
            value - running_mean - delta;

        minimum = std::min(
            minimum,
            cumulative
        );
        peak = std::max(
            peak,
            cumulative - minimum
        );
    }

    return clamp01(
        1.0 - std::exp(
            -peak / std::max(scale, 1e-9)
        )
    );
}

inline double adwin_score(
    std::span<const double> values,
    double delta = 0.01,
    std::size_t min_window = 3
) {
    min_window =
        std::max<std::size_t>(1, min_window);

    if (values.size() < 2 * min_window) {
        return 0.0;
    }

    std::vector<double> prefix(
        values.size() + 1,
        0.0
    );
    for (std::size_t index = 0; index < values.size(); ++index) {
        prefix[index + 1] =
            prefix[index] +
            clamp01(values[index]);
    }

    const double confidence =
        std::clamp(delta, 1e-12, 0.5);
    const double log_term =
        std::log(4.0 / confidence);

    double strongest = 0.0;
    for (
        std::size_t cut = min_window;
        cut <= values.size() - min_window;
        ++cut
    ) {
        const double n0 =
            static_cast<double>(cut);
        const double n1 =
            static_cast<double>(
                values.size() - cut
            );

        const double mean0 =
            prefix[cut] / n0;
        const double mean1 =
            (prefix.back() - prefix[cut]) / n1;

        const double epsilon = std::sqrt(
            0.5 * log_term *
            (1.0 / n0 + 1.0 / n1)
        );

        const double excess =
            std::abs(mean1 - mean0) -
            epsilon;

        if (excess > 0.0) {
            strongest = std::max(
                strongest,
                excess / (1.0 + epsilon)
            );
        }
    }

    return clamp01(strongest * 2.5);
}

inline BocpdResult bernoulli_bocpd(
    std::span<const int> observations,
    double hazard = 0.08,
    double prior_alpha = 1.0,
    double prior_beta = 1.0,
    std::size_t max_run_length = 64
) {
    if (observations.empty()) {
        return {
            .reset_probability = 0.0,
            .expected_run_length = 0.0,
            .posterior = {1.0},
        };
    }

    hazard = std::clamp(
        hazard,
        1e-6,
        0.95
    );
    prior_alpha =
        std::max(prior_alpha, 1e-9);
    prior_beta =
        std::max(prior_beta, 1e-9);

    std::vector<double> probabilities{1.0};
    std::vector<double> alphas{prior_alpha};
    std::vector<double> betas{prior_beta};

    for (int raw : observations) {
        const double observation =
            raw == 0 ? 0.0 : 1.0;

        const std::size_t length =
            std::min(
                probabilities.size(),
                max_run_length + 1
            );
        const std::size_t next_size =
            std::min(
                length + 1,
                max_run_length + 1
            );

        std::vector<double> next_probability(
            next_size,
            0.0
        );
        std::vector<double> next_alpha(
            next_size,
            prior_alpha
        );
        std::vector<double> next_beta(
            next_size,
            prior_beta
        );

        const double prior_predictive =
            observation > 0.5
            ? prior_alpha /
                (prior_alpha + prior_beta)
            : prior_beta /
                (prior_alpha + prior_beta);

        const double previous_mass =
            std::accumulate(
                probabilities.begin(),
                probabilities.begin() +
                    static_cast<std::ptrdiff_t>(length),
                0.0
            );

        next_probability[0] =
            hazard *
            prior_predictive *
            previous_mass;

        next_alpha[0] =
            prior_alpha + observation;
        next_beta[0] =
            prior_beta + (1.0 - observation);

        for (
            std::size_t run_length = 0;
            run_length < length;
            ++run_length
        ) {
            const std::size_t target =
                run_length + 1;

            if (target >= next_size) {
                continue;
            }

            const double alpha =
                alphas[run_length];
            const double beta =
                betas[run_length];

            const double predictive =
                observation > 0.5
                ? alpha / (alpha + beta)
                : beta / (alpha + beta);

            next_probability[target] =
                probabilities[run_length] *
                predictive *
                (1.0 - hazard);

            next_alpha[target] =
                alpha + observation;
            next_beta[target] =
                beta + (1.0 - observation);
        }

        const double total =
            std::accumulate(
                next_probability.begin(),
                next_probability.end(),
                0.0
            );

        if (total <= 1e-15) {
            std::fill(
                next_probability.begin(),
                next_probability.end(),
                0.0
            );
            next_probability[0] = 1.0;
        } else {
            for (double& probability :
                 next_probability) {
                probability /= total;
            }
        }

        probabilities =
            std::move(next_probability);
        alphas =
            std::move(next_alpha);
        betas =
            std::move(next_beta);
    }

    double expected_run_length = 0.0;
    for (
        std::size_t index = 0;
        index < probabilities.size();
        ++index
    ) {
        expected_run_length +=
            static_cast<double>(index) *
            probabilities[index];
    }

    return {
        .reset_probability =
            clamp01(probabilities.front()),
        .expected_run_length =
            expected_run_length,
        .posterior =
            std::move(probabilities),
    };
}

inline double robust_jump_score(
    std::span<const double> values
) {
    if (values.size() < 2) return 0.0;

    const auto prior =
        values.first(values.size() - 1);
    const double center =
        robust::median(prior);
    const double scale =
        robust::mad(prior, center);

    return clamp01(
        std::abs(
            values.back() - center
        ) /
        (1.35 * std::max(scale, 1e-9))
    );
}

inline Gallery gallery(
    std::span<const double> impact_history,
    std::span<const int> change_history
) {
    std::vector<double> normalized;
    normalized.reserve(
        std::max(
            impact_history.size(),
            change_history.size()
        )
    );

    if (!impact_history.empty()) {
        for (double value : impact_history) {
            normalized.push_back(
                clamp01(value / 10.0)
            );
        }
    } else {
        for (int value : change_history) {
            normalized.push_back(
                value == 0 ? 0.0 : 1.0
            );
        }
    }

    const double bocpd =
        change_history.empty()
        ? 0.0
        : bernoulli_bocpd(
            change_history
        ).reset_probability;

    return Gallery::from_votes(
        "change-detection",
        {
            {
                "cusum",
                cusum_score(normalized),
            },
            {
                "page-hinkley",
                page_hinkley_score(normalized),
            },
            {
                "adwin",
                adwin_score(normalized),
            },
            {
                "bocpd-beta",
                bocpd,
            },
            {
                "robust-jump",
                robust_jump_score(normalized),
            },
            {
                "theil-sen",
                clamp01(
                    std::abs(
                        robust::theil_sen_slope(
                            normalized
                        )
                    ) * 4.0
                ),
            },
        }
    );
}

} // namespace upstreamradar::museum::change
