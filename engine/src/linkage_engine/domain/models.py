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
class Path:
    """A validated chain: `start -> steps[0..3] -> end`.

    Exactly `len(steps) + 1` weights and relations, one per edge.
    """

    start: str
    end: str
    steps: tuple[str, ...]
    weights: tuple[float, ...]
    relations: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        expected = len(self.steps) + 1
        if len(self.weights) != expected or len(self.relations) != expected:
            raise ValueError(
                f"path with {len(self.steps)} steps needs {expected} edges, "
                f"got {len(self.weights)} weights / {len(self.relations)} relations"
            )

    @property
    def nodes(self) -> tuple[str, ...]:
        """All six nodes, start to end."""
        return (self.start, *self.steps, self.end)

    @property
    def min_weight(self) -> float:
        return min(self.weights)

    @property
    def geometric_mean_weight(self) -> float:
        product = 1.0
        for w in self.weights:
            product *= w
        return product ** (1.0 / len(self.weights))


@dataclass(frozen=True, slots=True)
class Candidate:
    """A path plus its word bank, ranked and awaiting human review."""

    path: Path
    bank: tuple[str, ...]  # shuffled; contains the solution plus distractors
    quality: float
    score_breakdown: tuple[tuple[str, float], ...] = ()

    @property
    def solution(self) -> tuple[str, ...]:
        return self.path.steps

    @property
    def distractors(self) -> tuple[str, ...]:
        solution = set(self.path.steps)
        return tuple(w for w in self.bank if w not in solution)

    def content_hash(self) -> str:
        """Stable identity for review decisions (planning.md 7.7).

        Covers the endpoints, the ordered solution, and the bank as a set --
        so re-running `generate` with a different shuffle still recognises a
        puzzle a human has already judged.
        """
        import hashlib

        payload = "|".join(
            [self.path.start, self.path.end, ">".join(self.path.steps), ",".join(sorted(self.bank))]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class Puzzle:
    """A dated, numbered puzzle. This is the shipped shape (planning.md 3.1)."""

    id: int
    date: str  # ISO yyyy-mm-dd
    start: str
    end: str
    solution: tuple[str, ...]
    bank: tuple[str, ...]

    def to_payload(self, schema_version: int) -> dict:
        """The decoded JSON a client receives. `meta` is deliberately absent --
        it is stripped on export as dead payload weight (planning.md 3.1)."""
        return {
            "schemaVersion": schema_version,
            "id": self.id,
            "date": self.date,
            "start": self.start,
            "end": self.end,
            "solution": list(self.solution),
            "bank": list(self.bank),
        }


@dataclass(slots=True)
class FunnelCounts:
    """Survival funnel for `linkage diagnose` (planning.md 7.9.3).

    Mutable by design -- this is a tally, not a value object, and it is
    incremented on the hot path once per candidate path considered.
    """

    pairs_sampled: int = 0
    paths_found: int = 0
    no_se_edge: int = 0
    chordless: int = 0
    weight_gate: int = 0
    unique_bank: int = 0

    def as_rows(self) -> tuple[tuple[str, int], ...]:
        """The funnel proper: each row is a strict subset of the one above.

        `unique_bank` is deliberately NOT here. It counts bank *constructions*,
        and several can happen for one endpoint pair while only the best
        becomes a candidate -- so showing it as a funnel stage would print a
        percentage that means nothing.
        """
        return (
            ("5-edge paths found", self.paths_found),
            ("survive: no S-E edge", self.no_se_edge),
            ("survive: chordless", self.chordless),
            ("survive: min weight gate", self.weight_gate),
        )


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
