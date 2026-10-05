#pragma once

#include "model.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <map>
#include <set>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>

namespace upstreamradar::museum::sketches {

inline std::uint64_t hash64(
    std::uint64_t seed,
    std::string_view value
) {
    std::uint64_t hash =
        0xcbf29ce484222325ULL ^
        (
            seed *
            0x9e3779b97f4a7c15ULL
        );

    for (unsigned char byte : value) {
        hash ^= static_cast<std::uint64_t>(byte);
        hash *= 0x100000001b3ULL;
        hash ^= hash >> 32;
    }
    return hash;
}

inline std::vector<std::uint64_t>
minhash_signature(
    std::span<const std::string> values,
    std::size_t permutations = 64
) {
    std::set<std::string> unique(
        values.begin(),
        values.end()
    );

    if (unique.empty()) return {};
    permutations =
        std::max<std::size_t>(1, permutations);

    std::vector<std::uint64_t> signature;
    signature.reserve(permutations);

    for (
        std::size_t seed = 0;
        seed < permutations;
        ++seed
    ) {
        std::uint64_t minimum =
            std::numeric_limits<std::uint64_t>::max();

        for (const auto& value : unique) {
            minimum = std::min(
                minimum,
                hash64(seed, value)
            );
        }
        signature.push_back(minimum);
    }

    return signature;
}

inline double minhash_similarity(
    std::span<const std::uint64_t> left,
    std::span<const std::uint64_t> right
) {
    if (left.empty() && right.empty()) {
        return 1.0;
    }
    if (left.empty() || right.empty()) {
        return 0.0;
    }

    const std::size_t size =
        std::min(left.size(), right.size());

    std::size_t equal = 0;
    for (
        std::size_t index = 0;
        index < size;
        ++index
    ) {
        if (left[index] == right[index]) {
            ++equal;
        }
    }

    return static_cast<double>(equal) /
        static_cast<double>(size);
}

inline double exact_jaccard(
    std::span<const std::string> left,
    std::span<const std::string> right
) {
    const std::set<std::string> a(
        left.begin(),
        left.end()
    );
    const std::set<std::string> b(
        right.begin(),
        right.end()
    );

    if (a.empty() && b.empty()) {
        return 1.0;
    }

    std::size_t intersection = 0;
    for (const auto& value : a) {
        if (b.contains(value)) {
            ++intersection;
        }
    }

    std::set<std::string> combined = a;
    combined.insert(
        b.begin(),
        b.end()
    );

    return static_cast<double>(intersection) /
        static_cast<double>(
            std::max<std::size_t>(
                1,
                combined.size()
            )
        );
}

inline double dependency_novelty(
    std::span<const std::string> target,
    const std::vector<
        std::vector<std::string>
    >& peers,
    std::size_t permutations = 64
) {
    const auto signature =
        minhash_signature(
            target,
            permutations
        );

    if (signature.empty()) {
        return 0.0;
    }

    double maximum_similarity = 0.0;
    for (const auto& peer : peers) {
        const auto other =
            minhash_signature(
                peer,
                permutations
            );

        if (other.empty()) continue;

        maximum_similarity = std::max(
            maximum_similarity,
            minhash_similarity(
                signature,
                other
            )
        );
    }

    return clamp01(
        1.0 - maximum_similarity
    );
}

class BloomFilter {
public:
    BloomFilter(
        std::size_t bits = 4096,
        std::size_t hashes = 5
    )
        : bits_(bits),
          hashes_(hashes),
          bitmap_((bits + 7) / 8, 0) {
        if (bits_ == 0 || hashes_ == 0) {
            throw std::invalid_argument(
                "bits and hashes must be positive"
            );
        }
    }

    void add(std::string_view value) {
        for (
            std::size_t seed = 0;
            seed < hashes_;
            ++seed
        ) {
            const std::size_t position =
                static_cast<std::size_t>(
                    hash64(seed, value) % bits_
                );

            bitmap_[position / 8] |=
                static_cast<std::uint8_t>(
                    1U << (position % 8)
                );
        }
        ++count_;
    }

    [[nodiscard]]
    bool contains(
        std::string_view value
    ) const {
        for (
            std::size_t seed = 0;
            seed < hashes_;
            ++seed
        ) {
            const std::size_t position =
                static_cast<std::size_t>(
                    hash64(seed, value) % bits_
                );

            if (
                (
                    bitmap_[position / 8] &
                    static_cast<std::uint8_t>(
                        1U << (position % 8)
                    )
                ) == 0
            ) {
                return false;
            }
        }
        return true;
    }

    [[nodiscard]]
    double estimated_false_positive_rate()
    const {
        return std::pow(
            1.0 - std::exp(
                -
                static_cast<double>(hashes_) *
                static_cast<double>(count_) /
                static_cast<double>(bits_)
            ),
            static_cast<double>(hashes_)
        );
    }

private:
    std::size_t bits_;
    std::size_t hashes_;
    std::vector<std::uint8_t> bitmap_;
    std::size_t count_{0};
};

class CountMinSketch {
public:
    CountMinSketch(
        std::size_t width = 1024,
        std::size_t depth = 5
    )
        : width_(width),
          depth_(depth),
          table_(
              depth,
              std::vector<std::uint64_t>(
                  width,
                  0
              )
          ) {
        if (width_ == 0 || depth_ == 0) {
            throw std::invalid_argument(
                "width and depth must be positive"
            );
        }
    }

    void add(
        std::string_view key,
        std::uint64_t count = 1
    ) {
        for (
            std::size_t seed = 0;
            seed < depth_;
            ++seed
        ) {
            const std::size_t index =
                static_cast<std::size_t>(
                    hash64(seed, key) %
                    width_
                );

            const auto maximum =
                std::numeric_limits<
                    std::uint64_t
                >::max();

            if (
                maximum -
                table_[seed][index] <
                count
            ) {
                table_[seed][index] =
                    maximum;
            } else {
                table_[seed][index] +=
                    count;
            }
        }
    }

    [[nodiscard]]
    std::uint64_t estimate(
        std::string_view key
    ) const {
        auto minimum =
            std::numeric_limits<
                std::uint64_t
            >::max();

        for (
            std::size_t seed = 0;
            seed < depth_;
            ++seed
        ) {
            const std::size_t index =
                static_cast<std::size_t>(
                    hash64(seed, key) %
                    width_
                );

            minimum = std::min(
                minimum,
                table_[seed][index]
            );
        }

        return minimum;
    }

private:
    std::size_t width_;
    std::size_t depth_;
    std::vector<
        std::vector<std::uint64_t>
    > table_;
};

class HyperLogLog {
public:
    explicit HyperLogLog(
        std::uint8_t precision = 10
    )
        : precision_(precision),
          registers_(
              static_cast<std::size_t>(
                  1ULL << precision
              ),
              0
          ) {
        if (
            precision_ < 4 ||
            precision_ > 16
        ) {
            throw std::invalid_argument(
                "precision must be in [4,16]"
            );
        }
    }

    void add(
        std::string_view value
    ) {
        const auto hashed =
            hash64(0x484c4cULL, value);

        const auto mask =
            (1ULL << precision_) - 1ULL;

        const std::size_t index =
            static_cast<std::size_t>(
                hashed & mask
            );

        const std::uint64_t remainder =
            hashed >> precision_;

        const int width =
            64 -
            static_cast<int>(precision_);

        int rank = width + 1;
        if (remainder != 0) {
            const int leading =
                std::countl_zero(remainder) -
                static_cast<int>(precision_);

            rank = std::max(
                1,
                leading + 1
            );
        }

        registers_[index] =
            std::max(
                registers_[index],
                static_cast<std::uint8_t>(
                    std::min(rank, 255)
                )
            );
    }

    [[nodiscard]]
    double estimate() const {
        const double m =
            static_cast<double>(
                registers_.size()
            );

        double alpha =
            0.7213 /
            (1.0 + 1.079 / m);

        if (registers_.size() == 16) {
            alpha = 0.673;
        } else if (
            registers_.size() == 32
        ) {
            alpha = 0.697;
        } else if (
            registers_.size() == 64
        ) {
            alpha = 0.709;
        }

        double harmonic = 0.0;
        std::size_t zeros = 0;

        for (std::uint8_t reg : registers_) {
            harmonic += std::pow(
                2.0,
                -static_cast<int>(reg)
            );

            if (reg == 0) {
                ++zeros;
            }
        }

        double result =
            alpha *
            m *
            m /
            std::max(harmonic, 1e-12);

        if (
            result <= 2.5 * m &&
            zeros > 0
        ) {
            result =
                m *
                std::log(
                    m /
                    static_cast<double>(zeros)
                );
        }

        return result;
    }

private:
    std::uint8_t precision_;
    std::vector<std::uint8_t> registers_;
};

struct HeavyHitter {
    std::string key;
    std::uint64_t estimate{0};
    std::uint64_t error{0};
};

class SpaceSaving {
public:
    explicit SpaceSaving(
        std::size_t capacity = 32
    )
        : capacity_(capacity) {
        if (capacity_ == 0) {
            throw std::invalid_argument(
                "capacity must be positive"
            );
        }
    }

    void add(
        std::string key,
        std::uint64_t count = 1
    ) {
        if (count == 0) {
            throw std::invalid_argument(
                "count must be positive"
            );
        }

        if (auto iterator =
            counters_.find(key);
            iterator != counters_.end()) {
            iterator->second.first += count;
            return;
        }

        if (
            counters_.size() <
            capacity_
        ) {
            counters_[std::move(key)] =
                {count, 0};
            return;
        }

        auto victim =
            std::min_element(
                counters_.begin(),
                counters_.end(),
                [](const auto& left,
                   const auto& right) {
                    if (
                        left.second.first ==
                        right.second.first
                    ) {
                        return left.first <
                            right.first;
                    }
                    return left.second.first <
                        right.second.first;
                }
            );

        const auto minimum =
            victim->second.first;

        counters_.erase(victim);

        counters_[
            std::move(key)
        ] = {
            minimum + count,
            minimum,
        };
    }

    [[nodiscard]]
    std::vector<HeavyHitter>
    heavy_hitters() const {
        std::vector<HeavyHitter> out;
        out.reserve(counters_.size());

        for (const auto& [key, value] :
             counters_) {
            out.push_back(
                {
                    key,
                    value.first,
                    value.second,
                }
            );
        }

        std::sort(
            out.begin(),
            out.end(),
            [](
                const HeavyHitter& left,
                const HeavyHitter& right
            ) {
                if (
                    left.estimate ==
                    right.estimate
                ) {
                    return left.key <
                        right.key;
                }
                return left.estimate >
                    right.estimate;
            }
        );

        return out;
    }

private:
    std::size_t capacity_;
    std::map<
        std::string,
        std::pair<
            std::uint64_t,
            std::uint64_t
        >
    > counters_;
};

inline Gallery gallery(
    std::span<const std::string> target,
    const std::vector<
        std::vector<std::string>
    >& peers
) {
    const double minhash_novelty =
        dependency_novelty(
            target,
            peers,
            64
        );

    double exact_similarity = 0.0;
    if (!peers.empty()) {
        for (const auto& peer : peers) {
            exact_similarity +=
                exact_jaccard(
                    target,
                    peer
                );
        }

        exact_similarity /=
            static_cast<double>(
                peers.size()
            );
    }

    return Gallery::from_votes(
        "streaming-sketch",
        {
            {
                "minhash-novelty",
                minhash_novelty,
            },
            {
                "exact-jaccard-novelty",
                clamp01(
                    1.0 -
                    exact_similarity
                ),
            },
        }
    );
}

} // namespace upstreamradar::museum::sketches
