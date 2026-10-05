#pragma once

#include "model.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <map>
#include <set>
#include <span>
#include <string>
#include <utility>
#include <vector>

namespace upstreamradar::museum::optimization {

struct Item {
    std::string name;
    std::uint32_t cost{1};
    double utility{0.0};
    double novelty{0.0};
    double risk{0.0};
    std::set<std::string> tags;
    std::string ecosystem;
};

inline Item from_candidate(
    const Candidate& candidate
) {
    return {
        .name = candidate.name,
        .cost = candidate.cost,
        .utility = candidate.utility,
        .novelty =
            candidate.structural_novelty,
        .risk = candidate.tail_risk,
        .tags = candidate.tags,
        .ecosystem =
            candidate.ecosystem,
    };
}

inline std::vector<std::string>
exact_knapsack(
    std::span<const Item> items,
    std::uint32_t budget
) {
    struct State {
        double utility{0.0};
        std::vector<std::string> names;
    };

    std::vector<State> dp(
        static_cast<std::size_t>(
            budget
        ) + 1
    );

    for (const auto& item : items) {
        const auto cost =
            std::max<std::uint32_t>(
                1,
                item.cost
            );

        if (cost > budget) {
            continue;
        }

        for (
            std::uint32_t capacity =
                budget;
            capacity >= cost;
            --capacity
        ) {
            const auto& previous =
                dp[
                    static_cast<
                        std::size_t
                    >(
                        capacity -
                        cost
                    )
                ];

            State candidate =
                previous;

            candidate.utility +=
                item.utility;

            candidate.names.push_back(
                item.name
            );

            std::sort(
                candidate.names.begin(),
                candidate.names.end()
            );

            auto& current =
                dp[
                    static_cast<
                        std::size_t
                    >(capacity)
                ];

            const bool better =
                candidate.utility >
                    current.utility +
                    1e-12;

            const bool tie_break =
                std::abs(
                    candidate.utility -
                    current.utility
                ) <= 1e-12 &&
                candidate.names <
                    current.names;

            if (better || tie_break) {
                current =
                    std::move(
                        candidate
                    );
            }

            if (capacity == cost) {
                break;
            }
        }
    }

    const auto best =
        std::max_element(
            dp.begin(),
            dp.end(),
            [](
                const State& left,
                const State& right
            ) {
                if (
                    std::abs(
                        left.utility -
                        right.utility
                    ) <= 1e-12
                ) {
                    return left.names >
                        right.names;
                }

                return left.utility <
                    right.utility;
            }
        );

    return best == dp.end()
        ? std::vector<std::string>{}
        : best->names;
}

inline std::vector<std::string>
epsilon_pareto(
    std::span<const Item> items,
    double epsilon = 1e-6
) {
    epsilon =
        std::max(0.0, epsilon);

    const auto dominates =
        [epsilon](
            const Item& left,
            const Item& right
        ) {
            const bool weak =
                left.utility +
                    epsilon >=
                    right.utility &&
                left.novelty +
                    epsilon >=
                    right.novelty &&
                left.risk <=
                    right.risk +
                    epsilon;

            const bool strict =
                left.utility >
                    right.utility +
                    epsilon ||
                left.novelty >
                    right.novelty +
                    epsilon ||
                left.risk +
                    epsilon <
                    right.risk;

            return weak && strict;
        };

    std::vector<std::string>
        frontier;

    for (
        std::size_t index = 0;
        index < items.size();
        ++index
    ) {
        bool dominated = false;

        for (
            std::size_t other = 0;
            other < items.size();
            ++other
        ) {
            if (
                index != other &&
                dominates(
                    items[other],
                    items[index]
                )
            ) {
                dominated = true;
                break;
            }
        }

        if (!dominated) {
            frontier.push_back(
                items[index].name
            );
        }
    }

    std::sort(
        frontier.begin(),
        frontier.end()
    );

    return frontier;
}

inline std::set<std::string>
covered_tags(
    const std::set<std::string>&
        selected,
    const std::map<
        std::string,
        Item
    >& by_name
) {
    std::set<std::string> covered;

    for (const auto& name :
         selected) {
        if (const auto iterator =
            by_name.find(name);
            iterator != by_name.end()) {
            covered.insert(
                iterator->second.tags.begin(),
                iterator->second.tags.end()
            );
        }
    }

    return covered;
}

inline std::vector<std::string>
celf_select(
    std::span<const Item> items,
    std::uint32_t budget
) {
    std::map<std::string, Item>
        by_name;

    for (const auto& item : items) {
        by_name[item.name] = item;
    }

    std::set<std::string>
        selected;

    std::uint32_t spent = 0;

    struct Cached {
        double gain{0.0};
        std::size_t stamp{0};
    };

    const auto marginal =
        [&](
            const Item& item
        ) {
            const auto covered =
                covered_tags(
                    selected,
                    by_name
                );

            std::size_t new_tags = 0;

            for (const auto& tag :
                 item.tags) {
                if (
                    !covered.contains(
                        tag
                    )
                ) {
                    ++new_tags;
                }
            }

            return
                static_cast<double>(
                    new_tags
                ) +
                0.50 *
                    item.utility +
                0.25 *
                    item.novelty -
                0.15 *
                    item.risk;
        };

    std::map<std::string, Cached>
        cache;

    for (const auto& item : items) {
        cache[item.name] = {
            .gain = marginal(item),
            .stamp = 0,
        };
    }

    while (!cache.empty()) {
        auto best = cache.end();

        for (auto iterator =
                 cache.begin();
             iterator != cache.end();
             ++iterator) {
            const auto& item =
                by_name.at(
                    iterator->first
                );

            const double ratio =
                iterator->second.gain /
                static_cast<double>(
                    std::max<
                        std::uint32_t
                    >(
                        1,
                        item.cost
                    )
                );

            if (best == cache.end()) {
                best = iterator;
                continue;
            }

            const auto& best_item =
                by_name.at(
                    best->first
                );

            const double best_ratio =
                best->second.gain /
                static_cast<double>(
                    std::max<
                        std::uint32_t
                    >(
                        1,
                        best_item.cost
                    )
                );

            if (
                ratio > best_ratio ||
                (
                    ratio ==
                        best_ratio &&
                    (
                        iterator->second.gain >
                            best->second.gain ||
                        (
                            iterator->second.gain ==
                                best->second.gain &&
                            iterator->first <
                                best->first
                        )
                    )
                )
            ) {
                best = iterator;
            }
        }

        if (best == cache.end()) {
            break;
        }

        if (
            best->second.stamp !=
            selected.size()
        ) {
            best->second.gain =
                marginal(
                    by_name.at(
                        best->first
                    )
                );

            best->second.stamp =
                selected.size();

            continue;
        }

        const std::string name =
            best->first;

        const Cached entry =
            best->second;

        cache.erase(best);

        const auto& item =
            by_name.at(name);

        if (
            spent + item.cost >
            budget
        ) {
            continue;
        }

        if (!(entry.gain > 0.0)) {
            break;
        }

        selected.insert(name);

        spent += item.cost;
    }

    return {
        selected.begin(),
        selected.end(),
    };
}

inline double portfolio_utility(
    std::span<const std::string>
        selected,
    std::span<const Item> items,
    double coverage_bonus = 0.08,
    double redundancy_penalty = 0.10
) {
    std::map<std::string, Item>
        by_name;

    for (const auto& item : items) {
        by_name[item.name] = item;
    }

    double total = 0.0;

    std::map<
        std::string,
        std::size_t
    > tag_counts;

    for (const auto& name :
         selected) {
        const auto iterator =
            by_name.find(name);

        if (iterator == by_name.end()) {
            continue;
        }

        total +=
            iterator->second.utility;

        for (const auto& tag :
             iterator->second.tags) {
            ++tag_counts[tag];
        }
    }

    std::size_t duplicates = 0;

    for (const auto& [_, count] :
         tag_counts) {
        if (count > 1) {
            duplicates +=
                count - 1;
        }
    }

    return
        total +
        coverage_bonus *
            static_cast<double>(
                tag_counts.size()
            ) -
        redundancy_penalty *
            static_cast<double>(
                duplicates
            );
}

struct BeamResult {
    std::vector<std::string>
        selected;
    double objective{0.0};
    std::uint32_t spent{0};
};

inline BeamResult
constrained_beam(
    std::span<const Candidate>
        candidates,
    std::uint32_t budget,
    std::size_t beam_width = 128,
    std::size_t ecosystem_cap = 3,
    double coverage_bonus = 0.08,
    double redundancy_penalty = 0.10
) {
    std::vector<Item> items;

    items.reserve(
        candidates.size()
    );

    std::map<
        std::string,
        Candidate
    > by_name;

    for (const auto& candidate :
         candidates) {
        items.push_back(
            from_candidate(candidate)
        );

        by_name[candidate.name] =
            candidate;
    }

    std::vector<Candidate> ordered(
        candidates.begin(),
        candidates.end()
    );

    std::sort(
        ordered.begin(),
        ordered.end(),
        [](
            const Candidate& left,
            const Candidate& right
        ) {
            const double left_ratio =
                left.utility /
                static_cast<double>(
                    std::max<
                        std::uint32_t
                    >(
                        1,
                        left.cost
                    )
                );

            const double right_ratio =
                right.utility /
                static_cast<double>(
                    std::max<
                        std::uint32_t
                    >(
                        1,
                        right.cost
                    )
                );

            if (
                left_ratio ==
                right_ratio
            ) {
                return left.name <
                    right.name;
            }

            return left_ratio >
                right_ratio;
        }
    );

    struct State {
        std::vector<std::string>
            selected;
        std::uint32_t spent{0};
        double objective{0.0};
        std::map<
            std::string,
            std::size_t
        > ecosystem_counts;
    };

    std::vector<State> beam{
        {}
    };

    beam_width =
        std::max<std::size_t>(
            8,
            beam_width
        );

    ecosystem_cap =
        std::max<std::size_t>(
            1,
            ecosystem_cap
        );

    for (const auto& candidate :
         ordered) {
        auto next = beam;

        for (const auto& state :
             beam) {
            if (
                state.spent +
                    candidate.cost >
                budget
            ) {
                continue;
            }

            const auto current_count =
                state.ecosystem_counts
                    .contains(
                        candidate.ecosystem
                    )
                ? state
                    .ecosystem_counts
                    .at(
                        candidate.ecosystem
                    )
                : 0;

            if (
                current_count >=
                ecosystem_cap
            ) {
                continue;
            }

            State expanded = state;

            expanded.selected.push_back(
                candidate.name
            );

            std::sort(
                expanded.selected.begin(),
                expanded.selected.end()
            );

            expanded.spent +=
                candidate.cost;

            ++expanded
                .ecosystem_counts[
                    candidate.ecosystem
                ];

            expanded.objective =
                portfolio_utility(
                    expanded.selected,
                    items,
                    coverage_bonus,
                    redundancy_penalty
                );

            next.push_back(
                std::move(expanded)
            );
        }

        std::sort(
            next.begin(),
            next.end(),
            [](
                const State& left,
                const State& right
            ) {
                if (
                    left.objective ==
                    right.objective
                ) {
                    if (
                        left.spent ==
                        right.spent
                    ) {
                        return left.selected <
                            right.selected;
                    }

                    return left.spent <
                        right.spent;
                }

                return left.objective >
                    right.objective;
            }
        );

        std::set<
            std::vector<std::string>
        > seen;

        std::vector<State>
            deduplicated;

        for (auto& state : next) {
            if (
                seen.insert(
                    state.selected
                ).second
            ) {
                deduplicated.push_back(
                    std::move(state)
                );

                if (
                    deduplicated.size() >=
                    beam_width
                ) {
                    break;
                }
            }
        }

        beam =
            std::move(
                deduplicated
            );
    }

    if (beam.empty()) {
        return {};
    }

    const auto best =
        std::max_element(
            beam.begin(),
            beam.end(),
            [](
                const State& left,
                const State& right
            ) {
                if (
                    left.objective ==
                    right.objective
                ) {
                    if (
                        left.spent ==
                        right.spent
                    ) {
                        return left.selected >
                            right.selected;
                    }

                    return left.spent >
                        right.spent;
                }

                return left.objective <
                    right.objective;
            }
        );

    return {
        .selected = best->selected,
        .objective = best->objective,
        .spent = best->spent,
    };
}

} // namespace upstreamradar::museum::optimization
