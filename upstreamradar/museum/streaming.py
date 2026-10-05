from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from math import log
from typing import Iterable


def _hash64(seed: int, value: str) -> int:
    person = seed.to_bytes(8, "little", signed=False)
    return int.from_bytes(
        blake2b(value.encode("utf-8"), digest_size=8, person=person).digest(),
        "little",
    )


class BloomFilter:
    def __init__(self, bits: int = 4096, hashes: int = 5) -> None:
        if bits <= 0 or hashes <= 0:
            raise ValueError("bits and hashes must be positive")
        self.bits = bits
        self.hashes = hashes
        self._bitmap = bytearray((bits + 7) // 8)
        self.count = 0

    def _positions(self, value: str):
        for seed in range(self.hashes):
            yield _hash64(seed, value) % self.bits

    def add(self, value: str) -> None:
        for position in self._positions(value):
            self._bitmap[position // 8] |= 1 << (position % 8)
        self.count += 1

    def __contains__(self, value: str) -> bool:
        return all(
            self._bitmap[position // 8] & (1 << (position % 8))
            for position in self._positions(value)
        )

    def estimated_false_positive_rate(self) -> float:
        return (1.0 - pow(2.718281828459045, -self.hashes * self.count / self.bits)) ** self.hashes


class CountMinSketch:
    def __init__(self, width: int = 1024, depth: int = 5) -> None:
        if width <= 0 or depth <= 0:
            raise ValueError("width and depth must be positive")
        self.width = width
        self.depth = depth
        self.table = [[0] * width for _ in range(depth)]

    def add(self, key: str, count: int = 1) -> None:
        if count < 0:
            raise ValueError("count must be non-negative")
        for seed in range(self.depth):
            self.table[seed][_hash64(seed, key) % self.width] += count

    def estimate(self, key: str) -> int:
        return min(
            self.table[seed][_hash64(seed, key) % self.width]
            for seed in range(self.depth)
        )


class HyperLogLog:
    def __init__(self, precision: int = 8) -> None:
        if not 4 <= precision <= 16:
            raise ValueError("precision must be in [4,16]")
        self.precision = precision
        self.registers = [0] * (1 << precision)

    def add(self, value: str) -> None:
        hashed = _hash64(0x484C4C, value)
        index_mask = (1 << self.precision) - 1
        index = hashed & index_mask
        remainder = hashed >> self.precision
        width = 64 - self.precision
        if remainder == 0:
            rank = width + 1
        else:
            rank = width - remainder.bit_length() + 1
        self.registers[index] = max(self.registers[index], rank)

    def estimate(self) -> float:
        m = len(self.registers)
        if m == 16:
            alpha = 0.673
        elif m == 32:
            alpha = 0.697
        elif m == 64:
            alpha = 0.709
        else:
            alpha = 0.7213 / (1.0 + 1.079 / m)
        harmonic = sum(2.0 ** (-register) for register in self.registers)
        estimate = alpha * m * m / harmonic

        zeros = self.registers.count(0)
        if estimate <= 2.5 * m and zeros:
            estimate = m * log(m / zeros)
        return estimate


@dataclass(frozen=True)
class HeavyHitter:
    key: str
    estimate: int
    error: int


class SpaceSaving:
    def __init__(self, capacity: int = 32) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._counters: dict[str, tuple[int, int]] = {}

    def add(self, key: str, count: int = 1) -> None:
        if count <= 0:
            raise ValueError("count must be positive")
        if key in self._counters:
            estimate, error = self._counters[key]
            self._counters[key] = (estimate + count, error)
            return
        if len(self._counters) < self.capacity:
            self._counters[key] = (count, 0)
            return

        victim, (minimum, _) = min(
            self._counters.items(),
            key=lambda item: (item[1][0], item[0]),
        )
        del self._counters[victim]
        self._counters[key] = (minimum + count, minimum)

    def heavy_hitters(self) -> tuple[HeavyHitter, ...]:
        items = [
            HeavyHitter(key, estimate, error)
            for key, (estimate, error) in self._counters.items()
        ]
        return tuple(
            sorted(items, key=lambda item: (-item.estimate, item.key))
        )


def summarize_stream(values: Iterable[str]) -> dict[str, object]:
    bloom = BloomFilter()
    hll = HyperLogLog()
    cms = CountMinSketch()
    heavy = SpaceSaving()
    total = 0
    for value in values:
        total += 1
        bloom.add(value)
        hll.add(value)
        cms.add(value)
        heavy.add(value)
    return {
        "total": total,
        "cardinality_estimate": hll.estimate(),
        "heavy_hitters": heavy.heavy_hitters(),
        "bloom_false_positive_rate": bloom.estimated_false_positive_rate(),
    }
