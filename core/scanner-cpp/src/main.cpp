#include <algorithm>
#include <cstdlib>
#include <iomanip>
#include <iostream>

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
    const double score =
        0.35 * std::min(files / 50.0, 1.0) +
        0.35 * std::min(churn / 2500.0, 1.0) +
        0.30 * security;

    std::cout << std::fixed << std::setprecision(6) << std::clamp(score, 0.0, 1.0) << '\n';
    return 0;
}
