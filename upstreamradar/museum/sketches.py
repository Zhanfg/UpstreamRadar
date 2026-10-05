from __future__ import annotations

from hashlib import blake2b
from typing import Iterable, Sequence


def _hash64(seed: int, value: str) -> int:
    person = seed.to_bytes(8, "little", signed=False)
    digest = blake2b(
        value.encode("utf-8"),
        digest_size=8,
        person=person,
    ).digest()
    return int.from_bytes(digest, "little")


def minhash_signature(
    values: Iterable[str],
    *,
    permutations: int = 64,
) -> tuple[int, ...]:
    unique = tuple(sorted(set(values)))
    if not unique:
        return ()
    signature = []
    for seed in range(max(1, permutations)):
        signature.append(min(_hash64(seed, value) for value in unique))
    return tuple(signature)


def minhash_similarity(
    left: Sequence[int],
    right: Sequence[int],
) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    if size == 0:
        return 0.0
    equal = sum(1 for a, b in zip(left[:size], right[:size]) if a == b)
    return equal / size


def dependency_novelty(
    target: Iterable[str],
    peers: Iterable[Iterable[str]],
    *,
    permutations: int = 64,
) -> float:
    signature = minhash_signature(target, permutations=permutations)
    if not signature:
        return 0.0
    peer_signatures = [
        minhash_signature(peer, permutations=permutations)
        for peer in peers
    ]
    peer_signatures = [item for item in peer_signatures if item]
    if not peer_signatures:
        return 1.0
    maximum_similarity = max(
        minhash_similarity(signature, other)
        for other in peer_signatures
    )
    return max(0.0, min(1.0, 1.0 - maximum_similarity))
