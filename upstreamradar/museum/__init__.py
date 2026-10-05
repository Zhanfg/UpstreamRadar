"""Curated algorithm collection used by SKOPRÆD v1.

The museum is not a grab bag. Every exhibit has metadata, tests, and a
production role or an explicit benchmark/reference role.
"""

from .model import AlgorithmExhibit, MuseumEvidence
from .registry import EXHIBITS, exhibit
from .ensemble import build_museum_evidence

__all__ = [
    "AlgorithmExhibit",
    "MuseumEvidence",
    "EXHIBITS",
    "exhibit",
    "build_museum_evidence",
]
