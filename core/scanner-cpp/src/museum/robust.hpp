#pragma once

#include "model.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <span>
#include <vector>

namespace upstreamradar::museum::robust {

inline std::vector<double> finite(std::span<const double> values) {
    std::vector<double> out;
    out.reserve(values.size());
    for (double value : values) {
        if (std::isfinite(value)) out.push_back(value);
    }
    return out;
}

inline double median(std::span<const double> values) {
    auto xs = finite(values);
    if (xs.empty()) return 0.0;
    std::sort(xs.begin(), xs.end());
    const std::size_t middle = xs.size() / 2;
    if (xs.size() % 2 == 0) {
        return (xs[middle - 1] + xs[middle]) / 2.0;
    }
    return xs[middle];
}

inline double mad(
    std::span<const double> values,
    double center
) {
    auto xs = finite(values);
    if (xs.empty()) return 1.0;
    std::vector<double> deviations;
    deviations.reserve(xs.size());
    for (double value : xs) {
        deviations.push_back(std::abs(value - center));
    }
    return std::max(1e-9, 1.4826 * median(deviations));
}

inline double mad(std::span<const double> values) {
    return mad(values, median(values));
}

inline double huber_location(
    std::span<const double> values,
    double delta = 1.345,
    std::size_t iterations = 16
) {
    auto xs = finite(values);
    if (xs.empty()) return 0.0;

    double location = median(xs);
    const double scale = mad(xs, location);
    if (scale <= 1e-12) return location;

    for (std::size_t iteration = 0;
         iteration < std::max<std::size_t>(1, iterations);
         ++iteration) {
        const double threshold = std::max(delta, 1e-6) * scale;
        double numerator = 0.0;
        double denominator = 0.0;

        for (double value : xs) {
            const double residual = value - location;
            const double absolute = std::abs(residual);
            const double weight = absolute <= threshold
                ? 1.0
                : threshold / std::max(absolute, 1e-12);
            numerator += weight * value;
            denominator += weight;
        }

        const double updated =
            numerator / std::max(denominator, 1e-12);
        if (std::abs(updated - location) <=
            1e-9 * std::max(1.0, std::abs(location))) {
            return updated;
        }
        location = updated;
    }
    return location;
}

inline double hampel_outlier_fraction(
    std::span<const double> values,
    double threshold = 3.0
) {
    auto xs = finite(values);
    if (xs.empty()) return 0.0;
    const double center = median(xs);
    const double scale = mad(xs, center);
    if (scale <= 1e-12) return 0.0;

    std::size_t outliers = 0;
    for (double value : xs) {
        if (std::abs(value - center) > threshold * scale) {
            ++outliers;
        }
    }
    return static_cast<double>(outliers) /
        static_cast<double>(xs.size());
}

inline double theil_sen_slope(
    std::span<const double> values
) {
    auto xs = finite(values);
    if (xs.size() < 2) return 0.0;

    std::vector<double> slopes;
    slopes.reserve(xs.size() * (xs.size() - 1) / 2);
    for (std::size_t left = 0; left + 1 < xs.size(); ++left) {
        for (std::size_t right = left + 1; right < xs.size(); ++right) {
            slopes.push_back(
                (xs[right] - xs[left]) /
                static_cast<double>(right - left)
            );
        }
    }
    return median(slopes);
}

inline double trimmed_mean(
    std::span<const double> values,
    double fraction = 0.10
) {
    auto xs = finite(values);
    if (xs.empty()) return 0.0;
    std::sort(xs.begin(), xs.end());

    fraction = std::clamp(fraction, 0.0, 0.49);
    std::size_t trim = static_cast<std::size_t>(
        std::floor(static_cast<double>(xs.size()) * fraction)
    );
    trim = std::min(trim, xs.size() / 2);

    const auto first = xs.begin() +
        static_cast<std::ptrdiff_t>(trim);
    const auto last = xs.end() -
        static_cast<std::ptrdiff_t>(trim);
    const double total = std::accumulate(first, last, 0.0);
    return total / static_cast<double>(std::distance(first, last));
}

inline double winsorized_variance(
    std::span<const double> values,
    double clip_z = 3.5
) {
    auto xs = finite(values);
    if (xs.size() < 2) return 0.0;

    const double center = huber_location(xs);
    const double scale = mad(xs, center);
    const double low = center - std::max(0.0, clip_z) * scale;
    const double high = center + std::max(0.0, clip_z) * scale;

    std::vector<double> clipped;
    clipped.reserve(xs.size());
    for (double value : xs) {
        clipped.push_back(std::clamp(value, low, high));
    }

    const double mean =
        std::accumulate(clipped.begin(), clipped.end(), 0.0) /
        static_cast<double>(clipped.size());
    double variance = 0.0;
    for (double value : clipped) {
        const double delta = value - mean;
        variance += delta * delta;
    }
    return variance /
        static_cast<double>(clipped.size() - 1);
}

inline double robust_activity(
    std::span<const double> features
) {
    if (features.empty()) return 0.0;
    const double huber = huber_location(features);
    const double trimmed = trimmed_mean(features);
    const double outliers =
        hampel_outlier_fraction(features);
    const double blend =
        0.58 * huber + 0.42 * trimmed;

    return clamp01(
        stable_sigmoid(blend) *
        (1.0 - 0.12 * outliers)
    );
}

inline Gallery gallery(
    std::span<const double> features
) {
    const double huber = clamp01(
        stable_sigmoid(huber_location(features))
    );
    const double trimmed = clamp01(
        stable_sigmoid(trimmed_mean(features))
    );
    const double cleanliness = clamp01(
        1.0 - hampel_outlier_fraction(features)
    );
    const double slope = clamp01(
        std::abs(theil_sen_slope(features))
    );

    return Gallery::from_votes(
        "robust-statistics",
        {
            {"huber", huber},
            {"trimmed-mean", trimmed},
            {"hampel-cleanliness", cleanliness},
            {"theil-sen", slope},
        }
    );
}

} // namespace upstreamradar::museum::robust
