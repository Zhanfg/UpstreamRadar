#pragma once

#include "model.hpp"

#include <algorithm>
#include <cmath>
#include <deque>
#include <map>
#include <queue>
#include <set>
#include <span>
#include <stack>
#include <string>
#include <utility>
#include <vector>

namespace upstreamradar::museum::graph {

using Graph = std::map<
    std::string,
    std::vector<std::string>
>;

inline std::vector<std::string>
nodes(const Graph& graph) {
    std::set<std::string> unique;

    for (const auto& [source, targets] :
         graph) {
        unique.insert(source);

        for (const auto& target : targets) {
            unique.insert(target);
        }
    }

    return {
        unique.begin(),
        unique.end(),
    };
}

inline std::vector<std::string>
normalized_targets(
    const Graph& graph,
    const std::string& source,
    const std::set<std::string>& known
) {
    std::set<std::string> unique;

    if (const auto iterator =
        graph.find(source);
        iterator != graph.end()) {
        for (const auto& target :
             iterator->second) {
            if (
                target != source &&
                known.contains(target)
            ) {
                unique.insert(target);
            }
        }
    }

    return {
        unique.begin(),
        unique.end(),
    };
}

inline Graph from_signals(
    std::span<const RepositorySignal> records
) {
    Graph graph;

    for (const auto& record : records) {
        graph[record.name] =
            record.normalized_dependencies();
    }

    return graph;
}

inline std::map<std::string, double>
pagerank(
    const Graph& graph,
    double damping = 0.85,
    std::size_t steps = 48,
    const std::map<
        std::string,
        double
    >& seeds = {}
) {
    const auto vertices = nodes(graph);

    if (vertices.empty()) {
        return {};
    }

    const std::set<std::string> known(
        vertices.begin(),
        vertices.end()
    );

    std::map<std::string, double> raw;
    double total = 0.0;

    for (const auto& vertex : vertices) {
        const auto iterator =
            seeds.find(vertex);

        const double value =
            iterator == seeds.end()
            ? 1.0
            : std::max(
                iterator->second,
                1e-12
            );

        raw[vertex] = value;
        total += value;
    }

    std::map<std::string, double>
        teleport;

    for (const auto& vertex : vertices) {
        teleport[vertex] =
            raw[vertex] /
            std::max(total, 1e-12);
    }

    auto rank = teleport;

    damping = std::clamp(
        damping,
        0.0,
        0.999999
    );

    steps = std::max<std::size_t>(
        1,
        steps
    );

    for (
        std::size_t iteration = 0;
        iteration < steps;
        ++iteration
    ) {
        std::map<std::string, double>
            next;

        for (const auto& vertex :
             vertices) {
            next[vertex] =
                (1.0 - damping) *
                teleport[vertex];
        }

        double dangling = 0.0;

        for (const auto& source :
             vertices) {
            const auto targets =
                normalized_targets(
                    graph,
                    source,
                    known
                );

            const double source_rank =
                rank[source];

            if (targets.empty()) {
                dangling += source_rank;
                continue;
            }

            const double share =
                damping *
                source_rank /
                static_cast<double>(
                    targets.size()
                );

            for (const auto& target :
                 targets) {
                next[target] += share;
            }
        }

        if (dangling > 0.0) {
            for (const auto& vertex :
                 vertices) {
                next[vertex] +=
                    damping *
                    dangling *
                    teleport[vertex];
            }
        }

        rank = std::move(next);
    }

    const double scale =
        std::accumulate(
            rank.begin(),
            rank.end(),
            0.0,
            [](
                double sum,
                const auto& entry
            ) {
                return sum +
                    entry.second;
            }
        );

    for (auto& [_, value] : rank) {
        value /=
            std::max(scale, 1e-12);
    }

    return rank;
}

inline std::pair<
    std::map<std::string, double>,
    std::map<std::string, double>
>
hits(
    const Graph& graph,
    std::size_t steps = 32
) {
    const auto vertices = nodes(graph);

    if (vertices.empty()) {
        return {{}, {}};
    }

    const std::set<std::string> known(
        vertices.begin(),
        vertices.end()
    );

    std::map<
        std::string,
        std::vector<std::string>
    > incoming;

    std::map<
        std::string,
        std::vector<std::string>
    > outgoing;

    for (const auto& vertex :
         vertices) {
        incoming[vertex] = {};
    }

    for (const auto& source :
         vertices) {
        auto targets =
            normalized_targets(
                graph,
                source,
                known
            );

        for (const auto& target :
             targets) {
            incoming[target].push_back(
                source
            );
        }

        outgoing[source] =
            std::move(targets);
    }

    std::map<std::string, double>
        hubs;

    std::map<std::string, double>
        authorities;

    for (const auto& vertex :
         vertices) {
        hubs[vertex] = 1.0;
        authorities[vertex] = 1.0;
    }

    const auto normalize_l2 =
        [](std::map<
               std::string,
               double
           > values) {
            double norm = 0.0;

            for (const auto& [_, value] :
                 values) {
                norm += value * value;
            }

            norm =
                std::sqrt(
                    std::max(
                        norm,
                        1e-24
                    )
                );

            for (auto& [_, value] :
                 values) {
                value /= norm;
            }

            return values;
        };

    for (
        std::size_t iteration = 0;
        iteration <
            std::max<std::size_t>(
                1,
                steps
            );
        ++iteration
    ) {
        std::map<std::string, double>
            next_authorities;

        for (const auto& vertex :
             vertices) {
            double value = 0.0;

            for (const auto& source :
                 incoming[vertex]) {
                value += hubs[source];
            }

            next_authorities[vertex] =
                value;
        }

        next_authorities =
            normalize_l2(
                std::move(
                    next_authorities
                )
            );

        std::map<std::string, double>
            next_hubs;

        for (const auto& vertex :
             vertices) {
            double value = 0.0;

            for (const auto& target :
                 outgoing[vertex]) {
                value +=
                    next_authorities[
                        target
                    ];
            }

            next_hubs[vertex] =
                value;
        }

        hubs =
            normalize_l2(
                std::move(next_hubs)
            );

        authorities =
            std::move(
                next_authorities
            );
    }

    return {
        std::move(hubs),
        std::move(authorities),
    };
}

inline std::map<std::string, double>
katz(
    const Graph& graph,
    double alpha = 0.0,
    double beta = 1.0,
    std::size_t steps = 40
) {
    const auto vertices = nodes(graph);

    if (vertices.empty()) {
        return {};
    }

    const std::set<std::string> known(
        vertices.begin(),
        vertices.end()
    );

    std::map<
        std::string,
        std::vector<std::string>
    > incoming;

    for (const auto& vertex :
         vertices) {
        incoming[vertex] = {};
    }

    std::size_t maximum_degree = 1;

    for (const auto& source :
         vertices) {
        const auto targets =
            normalized_targets(
                graph,
                source,
                known
            );

        maximum_degree =
            std::max(
                maximum_degree,
                targets.size()
            );

        for (const auto& target :
             targets) {
            incoming[target].push_back(
                source
            );
        }
    }

    if (!(alpha > 0.0)) {
        alpha =
            0.85 /
            static_cast<double>(
                maximum_degree
            );
    }

    std::map<std::string, double>
        scores;

    for (const auto& vertex :
         vertices) {
        scores[vertex] = 1.0;
    }

    for (
        std::size_t iteration = 0;
        iteration <
            std::max<std::size_t>(
                1,
                steps
            );
        ++iteration
    ) {
        std::map<std::string, double>
            next;

        double maximum = 0.0;

        for (const auto& vertex :
             vertices) {
            double value = beta;

            for (const auto& source :
                 incoming[vertex]) {
                value +=
                    alpha *
                    scores[source];
            }

            next[vertex] = value;

            maximum = std::max(
                maximum,
                value
            );
        }

        maximum =
            std::max(
                maximum,
                1e-12
            );

        for (auto& [_, value] :
             next) {
            value /= maximum;
        }

        scores = std::move(next);
    }

    return scores;
}

inline std::vector<
    std::vector<std::string>
>
tarjan_scc(
    const Graph& graph
) {
    const auto vertices =
        nodes(graph);

    const std::set<std::string> known(
        vertices.begin(),
        vertices.end()
    );

    std::size_t index = 0;
    std::vector<std::string> stack;
    std::set<std::string> on_stack;

    std::map<std::string, std::size_t>
        indices;

    std::map<std::string, std::size_t>
        lowlink;

    std::vector<
        std::vector<std::string>
    > components;

    const auto visit =
        [&](
            auto&& self,
            const std::string& vertex
        ) -> void {
            indices[vertex] = index;
            lowlink[vertex] = index;
            ++index;

            stack.push_back(vertex);
            on_stack.insert(vertex);

            const auto targets =
                normalized_targets(
                    graph,
                    vertex,
                    known
                );

            for (const auto& target :
                 targets) {
                if (!indices.contains(target)) {
                    self(
                        self,
                        target
                    );

                    lowlink[vertex] =
                        std::min(
                            lowlink[vertex],
                            lowlink[target]
                        );
                } else if (
                    on_stack.contains(
                        target
                    )
                ) {
                    lowlink[vertex] =
                        std::min(
                            lowlink[vertex],
                            indices[target]
                        );
                }
            }

            if (
                lowlink[vertex] ==
                indices[vertex]
            ) {
                std::vector<std::string>
                    component;

                while (!stack.empty()) {
                    const auto member =
                        stack.back();

                    stack.pop_back();
                    on_stack.erase(
                        member
                    );

                    component.push_back(
                        member
                    );

                    if (member == vertex) {
                        break;
                    }
                }

                std::sort(
                    component.begin(),
                    component.end()
                );

                components.push_back(
                    std::move(component)
                );
            }
        };

    for (const auto& vertex :
         vertices) {
        if (!indices.contains(vertex)) {
            visit(
                visit,
                vertex
            );
        }
    }

    std::sort(
        components.begin(),
        components.end(),
        [](
            const auto& left,
            const auto& right
        ) {
            if (
                left.empty() ||
                right.empty()
            ) {
                return left.size() <
                    right.size();
            }

            if (
                left.front() ==
                right.front()
            ) {
                return left.size() <
                    right.size();
            }

            return left.front() <
                right.front();
        }
    );

    return components;
}

inline std::map<std::string, double>
brandes_betweenness(
    const Graph& graph
) {
    const auto vertices =
        nodes(graph);

    const std::set<std::string> known(
        vertices.begin(),
        vertices.end()
    );

    std::map<std::string, double>
        score;

    for (const auto& vertex :
         vertices) {
        score[vertex] = 0.0;
    }

    for (const auto& source :
         vertices) {
        std::vector<std::string>
            stack;

        std::map<
            std::string,
            std::vector<std::string>
        > predecessors;

        std::map<std::string, double>
            sigma;

        std::map<std::string, int>
            distance;

        for (const auto& vertex :
             vertices) {
            predecessors[vertex] = {};
            sigma[vertex] = 0.0;
            distance[vertex] = -1;
        }

        sigma[source] = 1.0;
        distance[source] = 0;

        std::deque<std::string>
            queue{source};

        while (!queue.empty()) {
            const auto vertex =
                queue.front();

            queue.pop_front();

            stack.push_back(vertex);

            const auto targets =
                normalized_targets(
                    graph,
                    vertex,
                    known
                );

            for (const auto& target :
                 targets) {
                if (
                    distance[target] < 0
                ) {
                    queue.push_back(
                        target
                    );

                    distance[target] =
                        distance[vertex] +
                        1;
                }

                if (
                    distance[target] ==
                    distance[vertex] + 1
                ) {
                    sigma[target] +=
                        sigma[vertex];

                    predecessors[target]
                        .push_back(
                            vertex
                        );
                }
            }
        }

        std::map<std::string, double>
            dependency;

        for (const auto& vertex :
             vertices) {
            dependency[vertex] = 0.0;
        }

        while (!stack.empty()) {
            const auto target =
                stack.back();

            stack.pop_back();

            if (sigma[target] > 0.0) {
                const double coefficient =
                    (
                        1.0 +
                        dependency[target]
                    ) /
                    sigma[target];

                for (const auto& predecessor :
                     predecessors[target]) {
                    dependency[predecessor] +=
                        sigma[predecessor] *
                        coefficient;
                }
            }

            if (target != source) {
                score[target] +=
                    dependency[target];
            }
        }
    }

    double maximum = 0.0;

    for (const auto& [_, value] :
         score) {
        maximum =
            std::max(
                maximum,
                value
            );
    }

    maximum =
        std::max(
            maximum,
            1e-12
        );

    for (auto& [_, value] :
         score) {
        value /= maximum;
    }

    return score;
}

inline std::map<std::string, double>
k_core(
    const Graph& graph
) {
    const auto vertices =
        nodes(graph);

    std::map<
        std::string,
        std::set<std::string>
    > adjacency;

    for (const auto& vertex :
         vertices) {
        adjacency[vertex] = {};
    }

    for (const auto& [source, targets] :
         graph) {
        for (const auto& target :
             targets) {
            if (
                source == target ||
                !adjacency.contains(target)
            ) {
                continue;
            }

            adjacency[source].insert(
                target
            );

            adjacency[target].insert(
                source
            );
        }
    }

    std::map<std::string, std::size_t>
        degree;

    for (const auto& [vertex, neighbors] :
         adjacency) {
        degree[vertex] =
            neighbors.size();
    }

    std::set<std::string> removed;

    std::map<std::string, std::size_t>
        core;

    std::size_t degeneracy = 0;

    while (
        removed.size() <
        adjacency.size()
    ) {
        auto candidate =
            degree.end();

        for (auto iterator =
                 degree.begin();
             iterator != degree.end();
             ++iterator) {
            if (
                removed.contains(
                    iterator->first
                )
            ) {
                continue;
            }

            if (
                candidate == degree.end() ||
                iterator->second <
                    candidate->second ||
                (
                    iterator->second ==
                        candidate->second &&
                    iterator->first <
                        candidate->first
                )
            ) {
                candidate = iterator;
            }
        }

        if (candidate == degree.end()) {
            break;
        }

        const auto vertex =
            candidate->first;

        const auto current_degree =
            candidate->second;

        removed.insert(vertex);

        degeneracy =
            std::max(
                degeneracy,
                current_degree
            );

        core[vertex] = degeneracy;

        for (const auto& neighbor :
             adjacency[vertex]) {
            if (
                removed.contains(
                    neighbor
                )
            ) {
                continue;
            }

            if (degree[neighbor] > 0) {
                --degree[neighbor];
            }
        }
    }

    std::size_t maximum = 1;

    for (const auto& [_, value] :
         core) {
        maximum =
            std::max(
                maximum,
                value
            );
    }

    std::map<std::string, double>
        out;

    for (const auto& vertex :
         vertices) {
        out[vertex] =
            static_cast<double>(
                core[vertex]
            ) /
            static_cast<double>(
                maximum
            );
    }

    return out;
}

inline std::map<
    std::string,
    Gallery
>
galleries(
    const Graph& graph,
    const std::map<
        std::string,
        double
    >& seeds = {}
) {
    const auto pr =
        pagerank(
            graph,
            0.85,
            48,
            seeds
        );

    const auto [
        hubs,
        authorities
    ] = hits(graph);

    const auto kz =
        katz(graph);

    const auto between =
        brandes_betweenness(
            graph
        );

    const auto core =
        k_core(graph);

    const auto components =
        tarjan_scc(graph);

    std::set<std::string> cyclic;

    for (const auto& component :
         components) {
        if (component.size() > 1) {
            cyclic.insert(
                component.begin(),
                component.end()
            );
        }
    }

    const auto normalized_at =
        [](
            const auto& values,
            const std::string& key
        ) {
            double maximum = 0.0;

            for (const auto& [_, value] :
                 values) {
                maximum =
                    std::max(
                        maximum,
                        value
                    );
            }

            if (!(maximum > 0.0)) {
                return 0.0;
            }

            if (const auto iterator =
                values.find(key);
                iterator != values.end()) {
                return iterator->second /
                    maximum;
            }

            return 0.0;
        };

    std::map<
        std::string,
        Gallery
    > out;

    for (const auto& vertex :
         nodes(graph)) {
        out[vertex] =
            Gallery::from_votes(
                "graph",
                {
                    {
                        "pagerank",
                        normalized_at(
                            pr,
                            vertex
                        ),
                    },
                    {
                        "hits-hub",
                        normalized_at(
                            hubs,
                            vertex
                        ),
                    },
                    {
                        "hits-authority",
                        normalized_at(
                            authorities,
                            vertex
                        ),
                    },
                    {
                        "katz",
                        kz.contains(vertex)
                        ? kz.at(vertex)
                        : 0.0,
                    },
                    {
                        "brandes",
                        between.contains(vertex)
                        ? between.at(vertex)
                        : 0.0,
                    },
                    {
                        "k-core",
                        core.contains(vertex)
                        ? core.at(vertex)
                        : 0.0,
                    },
                    {
                        "tarjan-cycle",
                        cyclic.contains(vertex)
                        ? 1.0
                        : 0.0,
                    },
                }
            );
    }

    return out;
}

} // namespace upstreamradar::museum::graph
