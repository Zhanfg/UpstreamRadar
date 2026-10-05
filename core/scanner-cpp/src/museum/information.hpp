#pragma once

#include "model.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <span>
#include <vector>

namespace upstreamradar::museum::information {

inline std::vector<double> normalize(
    std::span<const double> values
) {
    if (values.empty()) return {};
    std::vector<double> out;
    out.reserve(values.size());

    double total = 0.0;
    for (double value : values) {
        const double positive = std::max(0.0, value);
        out.push_back(positive);
        total += positive;
    }

    if (total <= 1e-12) {
        const double uniform =
            1.0 / static_cast<double>(out.size());
        std::fill(out.begin(), out.end(), uniform);
        return out;
    }
    for (double& value : out) value /= total;
    return out;
}

inline double entropy(
    std::span<const double> values
) {
    const auto probabilities = normalize(values);
    double result = 0.0;
    for (double probability : probabilities) {
        if (probability > 1e-12) {
            result -= probability * std::log2(probability);
        }
    }
    return result;
}

inline double kl_divergence(
    std::span<const double> left,
    std::span<const double> right
) {
    double result = 0.0;
    const std::size_t size =
        std::min(left.size(), right.size());
    for (std::size_t index = 0; index < size; ++index) {
        const double p = left[index];
        const double q = right[index];
        if (p > 1e-12 && q > 1e-12) {
            result += p * std::log2(p / q);
        }
    }
    return result;
}

inline double jensen_shannon(
    std::span<const double> left,
    std::span<const double> right
) {
    const std::size_t size =
        std::max(left.size(), right.size());
    if (size == 0) return 0.0;

    std::vector<double> l(size, 0.0);
    std::vector<double> r(size, 0.0);
    std::copy(left.begin(), left.end(), l.begin());
    std::copy(right.begin(), right.end(), r.begin());
    l = normalize(l);
    r = normalize(r);

    std::vector<double> midpoint(size, 0.0);
    for (std::size_t index = 0; index < size; ++index) {
        midpoint[index] = (l[index] + r[index]) / 2.0;
    }

    return clamp01(
        0.5 * kl_divergence(l, midpoint) +
        0.5 * kl_divergence(r, midpoint)
    );
}

inline double quantile(
    std::span<const double> sorted,
    double q
) {
    if (sorted.empty()) return 0.0;
    if (sorted.size() == 1) return sorted.front();

    const double position = clamp01(q) *
        static_cast<double>(sorted.size() - 1);
    const auto lower = static_cast<std::size_t>(
        std::floor(position)
    );
    const auto upper = std::min(
        sorted.size() - 1,
        lower + 1
    );
    const double fraction =
        position - static_cast<double>(lower);
    return sorted[lower] * (1.0 - fraction) +
        sorted[upper] * fraction;
}

inline double wasserstein_1d(
    std::span<const double> left,
    std::span<const double> right
) {
    if (left.empty() && right.empty()) return 0.0;
    if (left.empty() || right.empty()) return 1.0;

    std::vector<double> a;
    std::vector<double> b;
    a.reserve(left.size());
    b.reserve(right.size());
    for (double value : left) a.push_back(clamp01(value));
    for (double value : right) b.push_back(clamp01(value));
    std::sort(a.begin(), a.end());
    std::sort(b.begin(), b.end());

    const std::size_t samples = std::max<std::size_t>(
        2,
        std::max(a.size(), b.size())
    );
    double total = 0.0;
    for (std::size_t index = 0; index < samples; ++index) {
        const double q =
            static_cast<double>(index) /
            static_cast<double>(samples - 1);
        total += std::abs(
            quantile(a, q) -
            quantile(b, q)
        );
    }
    return clamp01(
        total / static_cast<double>(samples)
    );
}

inline double median(
    std::vector<double> values
) {
    if (values.empty()) return 0.1;
    std::sort(values.begin(), values.end());
    const std::size_t middle = values.size() / 2;
    if (values.size() % 2 == 0) {
        return (
            values[middle - 1] +
            values[middle]
        ) / 2.0;
    }
    return values[middle];
}

inline double maximum_mean_discrepancy(
    std::span<const double> left,
    std::span<const double> right,
    double bandwidth = 0.0
) {
    if (left.empty() && right.empty()) return 0.0;
    if (left.empty() || right.empty()) return 1.0;

    std::vector<double> a;
    std::vector<double> b;
    a.reserve(left.size());
    b.reserve(right.size());
    for (double value : left) a.push_back(clamp01(value));
    for (double value : right) b.push_back(clamp01(value));

    if (!(bandwidth > 0.0)) {
        std::vector<double> combined = a;
        combined.insert(
            combined.end(),
            b.begin(),
            b.end()
        );

        std::vector<double> distances;
        for (std::size_t i = 0; i + 1 < combined.size(); ++i) {
            for (std::size_t j = i + 1; j < combined.size(); ++j) {
                const double distance =
                    std::abs(combined[i] - combined[j]);
                if (distance > 1e-12) {
                    distances.push_back(distance);
                }
            }
        }
        bandwidth = distances.empty()
            ? 0.1
            : median(std::move(distances));
    }
    bandwidth = std::max(1e-6, bandwidth);

    const auto kernel = [bandwidth](double x, double y) {
        const double distance = x - y;
        return std::exp(
            -(distance * distance) /
            (2.0 * bandwidth * bandwidth)
        );
    };

    const auto average_kernel =
        [&kernel](
            std::span<const double> first,
            std::span<const double> second
        ) {
            double total = 0.0;
            for (double x : first) {
                for (double y : second) {
                    total += kernel(x, y);
                }
            }
            return total /
                static_cast<double>(
                    first.size() * second.size()
                );
        };

    const double aa = average_kernel(a, a);
    const double bb = average_kernel(b, b);
    const double ab = average_kernel(a, b);
    const double mmd2 =
        std::max(0.0, aa + bb - 2.0 * ab);

    return clamp01(std::sqrt(mmd2 / 2.0));
}

inline std::vector<double> histogram(
    std::span<const double> values,
    std::size_t bins = 4
) {
    bins = std::max<std::size_t>(1, bins);
    std::vector<double> out(bins, 0.0);
    for (double value : values) {
        const auto index = std::min(
            bins - 1,
            static_cast<std::size_t>(
                std::floor(
                    clamp01(value) *
                    static_cast<double>(bins)
                )
            )
        );
        out[index] += 1.0;
    }
    return out;
}

inline Gallery gallery(
    std::span<const double> history
) {
    if (history.size() < 4) {
        return Gallery::from_votes(
            "information-distance",
            {
                {"jsd", 0.0},
                {"wasserstein-1", 0.0},
                {"mmd-rbf", 0.0},
            }
        );
    }

    const std::size_t split = std::min(
        history.size() - 1,
        std::max<std::size_t>(2, history.size() / 2)
    );
    const auto older = history.first(split);
    const auto recent = history.subspan(split);

    const auto older_histogram = histogram(older);
    const auto recent_histogram = histogram(recent);

    return Gallery::from_votes(
        "information-distance",
        {
            {
                "jsd",
                jensen_shannon(
                    older_histogram,
                    recent_histogram
                ),
            },
            {
                "wasserstein-1",
                wasserstein_1d(older, recent),
            },
            {
                "mmd-rbf",
                maximum_mean_discrepancy(
                    older,
                    recent
                ),
            },
        }
    );
}

} // namespace upstreamradar::museum::information
