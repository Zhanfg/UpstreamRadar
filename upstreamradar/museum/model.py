from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class AlgorithmExhibit:
    slug: str
    name: str
    family: str
    introduced: int
    complexity: str
    role: str
    production: bool
    notes: str = ""


@dataclass(frozen=True)
class MuseumEvidence:
    robust_activity: float
    change_consensus: float
    information_gain: float
    graph_consensus: float
    bandit_index: float
    dependency_novelty: float
    disagreement: float
    consensus: float
    trace: Tuple[Tuple[str, float], ...] = ()

    def bounded(self) -> bool:
        values = (
            self.robust_activity,
            self.change_consensus,
            self.information_gain,
            self.graph_consensus,
            self.bandit_index,
            self.dependency_novelty,
            self.disagreement,
            self.consensus,
        )
        return all(0.0 <= value <= 1.0 for value in values)
