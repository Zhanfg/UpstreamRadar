"""UpstreamRadar scheduling and content-planning primitives."""

from .content import ContentOpportunity, build_content_plan
from .engine import (
    CandidateScore,
    RepositorySignal,
    ScheduleResult,
    SkopraedConfig,
    SkopraedScheduler,
)

# Compatibility aliases remain importable for older callers but are excluded
# from __all__ so the active public identity is Skopraed.
HarmonyConfig = SkopraedConfig
HarmonyScheduler = SkopraedScheduler

__all__ = [
    "CandidateScore",
    "ContentOpportunity",
    "RepositorySignal",
    "ScheduleResult",
    "SkopraedConfig",
    "SkopraedScheduler",
    "build_content_plan",
]
