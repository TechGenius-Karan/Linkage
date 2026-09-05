"""Frozen value objects shared across the engine.

Domain tier: pure data, no I/O, no network, no filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Assertion:
    """One filtered, normalised ConceptNet edge.

    `start` and `end` are bare lowercase lemmas (no `/c/en/` prefix, no POS
    suffix). `relation` is the bare relation name (no `/r/` prefix).
    """

    start: str
    end: str
    relation: str
    weight: float


@dataclass(frozen=True, slots=True)
class VocabularyResult:
    """The surviving word set plus why everything else was dropped.

    The rejection breakdown is not decoration -- it is the feedback loop for
    tuning the filter chain, and it is printed by `linkage build-graph`.
    """

    words: frozenset[str]
    considered: int
    rejected_by: dict[str, int] = field(default_factory=dict)

    @property
    def kept(self) -> int:
        return len(self.words)


@dataclass(frozen=True, slots=True)
class GraphStats:
    """Summary of a built graph, for reporting and sanity checks."""

    nodes: int
    edges: int
    isolated_removed: int
    hubs_removed: int
    hub_degree_cutoff: int
    mean_degree: float
    median_degree: int
    max_degree: int
