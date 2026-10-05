#include <algorithm>
#include <cstdlib>
#include <iomanip>
#include <iostream>

#include "skopraed_legacy_v3.hpp"

int main(int argc, char** argv) {
    if (argc != 5) {
        std::cerr << "usage: change-score <files> <additions> <deletions> <security:0|1>\n";
        return 2;
    }

    const double files = std::max(0, std::atoi(argv[1]));
    const double additions = std::max(0, std::atoi(argv[2]));
    const double deletions = std::max(0, std::atoi(argv[3]));
    const double security = std::atoi(argv[4]) != 0 ? 1.0 : 0.0;

    const double churn = additions + deletions;
    const double dependency = std::min(files / 20.0, 1.0);
    const double novelty = std::min(std::log1p(churn) / std::log(2501.0), 1.0);
    const double score = upstreamradar::skopraed_legacy_v3::nonlinear_change_score(
        files,
        churn,
        security,
        dependency,
        novelty
    );

    std::cout << std::fixed << std::setprecision(6) << score << '\n';
    return 0;
}
