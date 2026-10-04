#pragma once

#include <algorithm>
#include <cmath>
#include <numeric>
#include <vector>

namespace upstreamradar::v3 {

inline double clamp01(double value) {
    return std::clamp(value, 0.0, 1.0);
}

inline double sigmoid(double value) {
    if (value >= 0.0) {
        const double z = std::exp(-value);
        return 1.0 / (1.0 + z);
    }
    const double z = std::exp(value);
    return z / (1.0 + z);
}

inline double bernoulli_kl(double q, double p) {
    constexpr double eps = 1e-12;
    q = std::clamp(q, eps, 1.0 - eps);
    p = std::clamp(p, eps, 1.0 - eps);
    return q * std::log(q / p) + (1.0 - q) * std::log((1.0 - q) / (1.0 - p));
}

inline double bayesian_surprise(double empirical, double predicted) {
    return clamp01(1.0 - std::exp(-3.4 * bernoulli_kl(empirical, predicted)));
}

inline double cvar(std::vector<double> values, double quantile = 0.75) {
    if (values.empty()) return 0.0;
    for (double& value : values) value = clamp01(value);
    std::sort(values.begin(), values.end());
    quantile = std::clamp(quantile, 0.5, 0.999999);
    const auto start = static_cast<std::size_t>(
        std::floor(static_cast<double>(values.size() - 1) * quantile)
    );
    const double total = std::accumulate(values.begin() + start, values.end(), 0.0);
    return total / static_cast<double>(values.size() - start);
}

inline double nonlinear_change_score(
    double files,
    double churn,
    double security,
    double dependency,
    double novelty
) {
    const double activity = 0.52 * clamp01(files / 50.0)
        + 0.48 * clamp01(churn / 2500.0);
    const double risk = 0.44 * clamp01(security)
        + 0.34 * clamp01(dependency)
        + 0.22 * clamp01(novelty);
    const double interaction = sigmoid(3.0 * (activity * risk - 0.25));
    return clamp01(0.38 * activity + 0.36 * risk + 0.26 * interaction);
}

} // namespace upstreamradar::v3
