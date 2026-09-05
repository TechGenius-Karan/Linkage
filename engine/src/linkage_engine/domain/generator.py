"""Turning paths into reviewable candidates (planning.md 7.6, 7.7).

Domain tier: pure. Orchestrates pathfinder + distractors + scorer without
performing any I/O of its own.

Single Responsibility note: this module *composes*. It does not know how a
path is found, how a distractor is chosen, or what makes a puzzle good --
each of those lives in its own module and can change without touching this
one.
"""

from __future__ import annotations

import random
from typing import Callable, Iterator

import networkx as nx

from ..config import Config
from .distractors import DistractorSelector
from .models import Candidate, Path
from .pathfinder import BidirectionalBFSFinder
from .scoring import QualityScorer


def shuffled_bank(bank: tuple[str, ...], puzzle_seed: int) -> tuple[str, ...]:
    """Deterministic bank order (planning.md 2.3).

    Shuffled at generation time, not in the client: tile positions must be
    stable across refreshes and identical for every player.
    """
    words = list(bank)
    random.Random(puzzle_seed).shuffle(words)
    return tuple(words)


class CandidateGenerator:
    """Produces scored, uniquely-solvable candidates for review."""

    def __init__(
        self,
        graph: nx.Graph,
        cfg: Config,
        rng: random.Random,
        selector: DistractorSelector,
        scorer: QualityScorer | None = None,
    ) -> None:
        self.graph = graph
        self.cfg = cfg
        self.rng = rng
        self.selector = selector
        self.scorer = scorer or QualityScorer()
        # The finder shares the selector's stemmer: morphological kin must be
        # rejected at the path level too, not only when picking distractors.
        self.finder = BidirectionalBFSFinder(graph, cfg, rng, selector.stemmer)

    @property
    def counts(self):
        return self.finder.counts

    def _best_for_pair(self, paths: list[Path]) -> Candidate | None:
        """One candidate per endpoint pair, the best-scoring one.

        planning.md 7.7.1 forbids duplicate (start, end) pairs across the
        year, so emitting several per pair would only queue up work that
        export would later reject. Deciding here is cheaper and keeps the
        review queue honest.
        """
        best: Candidate | None = None
        for path in paths:
            quality, breakdown = self.scorer.score(self.graph, path)
            if best is not None and quality <= best.quality:
                continue
            bank = self.selector.build_bank(self.graph, path)
            if bank is None:
                continue
            self.finder.counts.unique_bank += 1
            candidate = Candidate(
                path=path,
                bank=shuffled_bank(bank, self.rng.randrange(2**31)),
                quality=quality,
                score_breakdown=breakdown,
            )
            best = candidate
        return best

    def generate(
        self,
        wanted: int,
        max_pairs: int,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> Iterator[Candidate]:
        """Yield up to `wanted` candidates, trying at most `max_pairs` pairs.

        Both bounds matter. `wanted` is what we need; `max_pairs` stops a run
        that is finding nothing from looping forever on a graph that cannot
        satisfy the constraints.
        """
        emitted = 0
        seen_pairs: set[frozenset[str]] = set()

        for _ in range(max_pairs):
            if emitted >= wanted:
                return
            start, end = self.finder.sample_pair()
            pair = frozenset({start, end})
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            self.finder.counts.pairs_sampled += 1
            paths = self.finder.paths_between(start, end)
            if not paths:
                continue

            candidate = self._best_for_pair(paths)
            if candidate is None:
                continue

            emitted += 1
            if on_progress:
                on_progress(emitted, wanted)
            yield candidate
