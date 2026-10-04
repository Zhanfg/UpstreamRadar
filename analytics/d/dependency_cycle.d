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
