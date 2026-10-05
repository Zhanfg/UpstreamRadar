#include "change.hpp"
#include "graph.hpp"
#include "information.hpp"
#include "optimization.hpp"
#include "robust.hpp"
#include "sketches.hpp"

#include <cassert>
#include <cmath>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>

using namespace upstreamradar::museum;

int main() {
    {
        const std::vector<double> values{
            1.0,
            1.1,
            0.9,
            1.05,
            100.0,
        };

        const double location =
            robust::huber_location(values);

        const double mean =
            std::accumulate(
                values.begin(),
                values.end(),
                0.0
            ) /
            static_cast<double>(
                values.size()
            );

        assert(
            std::abs(location - 1.0) <
            std::abs(mean - 1.0)
        );
    }

    {
        std::vector<double> stable(
            48,
            0.1
        );

        std::vector<double> shifted(
            48,
            0.1
        );

        std::fill(
            shifted.begin() + 24,
            shifted.end(),
            0.9
        );

        assert(
            change::cusum_score(
                shifted
            ) >
            change::cusum_score(
                stable
            )
        );

        assert(
            change::adwin_score(
                shifted
            ) >
            change::adwin_score(
                stable
            )
        );
    }

    {
        const std::vector<double> left{
            0.0,
            0.1,
            0.2,
        };

        const std::vector<double> right{
            0.8,
            0.9,
            1.0,
        };

        assert(
            information::wasserstein_1d(
                left,
                right
            ) > 0.6
        );

        assert(
            information::maximum_mean_discrepancy(
                left,
                right
            ) > 0.3
        );
    }

    {
        graph::Graph topology{
            {
                "hub",
                {},
            },
            {
                "a",
                {"hub"},
            },
            {
                "b",
                {"hub"},
            },
            {
                "c",
                {
                    "hub",
                    "a",
                },
            },
        };

        const auto rank =
            graph::pagerank(
                topology
            );

        double total = 0.0;

        for (const auto& [_, value] :
             rank) {
            total += value;
        }

        assert(
            std::abs(total - 1.0) <
            1e-9
        );

        const auto galleries =
            graph::galleries(
                topology
            );

        assert(
            galleries.contains(
                "hub"
            )
        );

        for (const auto& [_, gallery] :
             galleries) {
            assert(
                gallery.consensus >=
                    0.0 &&
                gallery.consensus <=
                    1.0
            );
        }
    }

    {
        std::vector<std::string> a{
            "a",
            "b",
            "c",
        };

        std::vector<std::string> b = a;

        std::vector<std::string> c{
            "x",
            "y",
        };

        const auto signature_a =
            sketches::minhash_signature(
                a,
                128
            );

        const auto signature_b =
            sketches::minhash_signature(
                b,
                128
            );

        const auto signature_c =
            sketches::minhash_signature(
                c,
                128
            );

        assert(
            sketches::minhash_similarity(
                signature_a,
                signature_b
            ) == 1.0
        );

        assert(
            sketches::minhash_similarity(
                signature_a,
                signature_c
            ) < 0.5
        );

        sketches::BloomFilter filter(
            2048,
            5
        );

        for (const auto& value : a) {
            filter.add(value);
        }

        for (const auto& value : a) {
            assert(
                filter.contains(value)
            );
        }

        sketches::CountMinSketch cms(
            128,
            5
        );

        for (int index = 0;
             index < 20;
             ++index) {
            cms.add("hot");
        }

        assert(
            cms.estimate("hot") >=
            20
        );
    }

    {
        std::vector<
            optimization::Item
        > items{
            {
                "a",
                3,
                5.0,
                0.5,
                0.2,
                {"kernel"},
                "native",
            },
            {
                "b",
                2,
                3.0,
                0.8,
                0.1,
                {"network"},
                "go",
            },
            {
                "c",
                2,
                4.0,
                0.7,
                0.15,
                {"security"},
                "rust",
            },
        };

        const auto exact =
            optimization::exact_knapsack(
                items,
                4
            );

        assert(
            (
                exact ==
                std::vector<
                    std::string
                >{
                    "b",
                    "c",
                }
            )
        );

        const auto frontier =
            optimization::epsilon_pareto(
                items
            );

        assert(
            std::find(
                frontier.begin(),
                frontier.end(),
                "b"
            ) == frontier.end()
        );
    }

    std::cout
        << "museum_native_selftest=ok\n";

    return 0;
}
