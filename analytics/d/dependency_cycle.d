module dependency_cycle;

import std.algorithm : canFind;
import std.array : appender;
import std.string : toStringz;

alias Graph = string[][string];

bool hasCycle(const Graph graph) {
    int[string] state;

    bool visit(string node) {
        auto current = node in state;
        if (current !is null) {
            if (*current == 1) return true;
            if (*current == 2) return false;
        }

        state[node] = 1;
        auto children = node in graph;
        if (children !is null) {
            foreach (child; *children) {
                if (visit(child)) return true;
            }
        }
        state[node] = 2;
        return false;
    }

    foreach (node; graph.byKey) {
        if (visit(node)) return true;
    }
    return false;
}


double[string] seededRank(const Graph graph, const double[string] seeds, double damping = 0.84, size_t steps = 32) {
    import std.algorithm : max;
    import std.array : array;
    import std.math : fabs;
    import std.range : chain;
    import std.typecons : Tuple;

    bool[string] known;
    foreach (node; graph.byKey) known[node] = true;
    foreach (children; graph.byValue)
        foreach (child; children) known[child] = true;

    double total = 0.0;
    foreach (node; known.byKey) {
        auto seed = node in seeds;
        total += seed is null ? 1e-12 : max(*seed, 1e-12);
    }
    if (total <= 0.0) total = 1.0;

    double[string] teleport;
    double[string] rank;
    foreach (node; known.byKey) {
        auto seed = node in seeds;
        auto value = (seed is null ? 1e-12 : max(*seed, 1e-12)) / total;
        teleport[node] = value;
        rank[node] = value;
    }

    foreach (_; 0 .. steps) {
        double[string] next;
        foreach (node; known.byKey)
            next[node] = (1.0 - damping) * teleport[node];

        foreach (source; known.byKey) {
            auto children = source in graph;
            if (children is null || (*children).length == 0) {
                foreach (node; known.byKey)
                    next[node] += damping * rank[source] * teleport[node];
                continue;
            }
            auto share = damping * rank[source] / (*children).length;
            foreach (target; *children)
                next[target] += share;
        }
        rank = next;
    }
    return rank;
}
