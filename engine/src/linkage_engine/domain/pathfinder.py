"""Bidirectional bounded BFS over the concept graph (planning.md 7.4).

Domain tier: pure.

We need paths of exactly 5 edges (6 nodes). Naive BFS to depth 5 explodes;
meeting in the middle does not:

    S --> w1 --> w2        w3 <-- w4 <-- E
    |______________|        |______________|
     forward, depth 2        backward, depth 2
                    \\      /
                  bridge edge (w2, w3)

`PathFinder` is a Protocol on purpose. planning.md 7.9.4 Tier 5 argues that
BFS solves a harder problem than we have -- it is the right algorithm when
*given* S and E, but we generate both -- and that constructive growth would
be the swap if yield ever fell short. Phase 1 measured yield at 4.57M usable
paths per 1,000 seeds, so BFS stays; the seam stays open regardless, and it
costs one `Protocol` declaration.
"""

from __future__ import annotations

import itertools
import random
from typing import Iterator, Protocol

import networkx as nx

from ..config import Config
from .hubs import sorted_neighbours
from .models import FunnelCounts, Path
from .ports import Stemmer


class _ExactStemmer:
    """Fallback stemmer: only identical words collide.

    Keeps `has_stem_collision` meaningful (it still catches exact repeats)
    without forcing every test to construct a real stemmer.
    """

    def stem(self, word: str) -> str:
        return word


class PathFinder(Protocol):
    """Yields validated chains. Implementations differ in *how* they search."""

    def find(self, budget: int) -> Iterator[Path]: ...


# --------------------------------------------------------------------------
# Constraint predicates -- pure, and each independently testable
# --------------------------------------------------------------------------


def has_direct_se_edge(graph: nx.Graph, nodes: tuple[str, ...]) -> bool:
    """A start/end pair that already touch make the whole puzzle pointless."""
    return graph.has_edge(nodes[0], nodes[-1])


def chord_pairs(n: int) -> tuple[tuple[int, int], ...]:
    """Index pairs that must NOT be edges, excluding the start/end pair.

    For 6 nodes there are C(6,2)=15 pairs; 5 are the path itself and one is
    start/end (handled separately, since it is a spec requirement in its own
    right), leaving 9 chords.
    """
    return tuple(
        (i, j)
        for i, j in itertools.combinations(range(n), 2)
        if j - i > 1 and not (i == 0 and j == n - 1)
    )


def has_stem_collision(stemmer: Stemmer, nodes: tuple[str, ...]) -> bool:
    """Two words in the chain that are morphological kin.

    `STICK -> ... -> sticks -> ... -> SCREAM` is the exact "morphological, not
    conceptual" failure the relation blocklist targets (planning.md 7.2) --
    but that blocklist only removes `FormOf`/`DerivedFrom` *edges*, and two
    kin words can still be joined by a perfectly ordinary `RelatedTo`. The
    constraint has to be re-applied to the assembled chain.

    Found by reading real output: 7 of 900 candidates had a step echoing an
    endpoint, and 5 more had two steps echoing each other.
    """
    stems = [stemmer.stem(word) for word in nodes]
    return len(set(stems)) != len(stems)


def has_chord(graph: nx.Graph, nodes: tuple[str, ...]) -> bool:
    """Any shortcut between two non-adjacent members of the chain.

    Chordless does two jobs (planning.md 7.4): every rung becomes
    load-bearing, and -- because start touches only w1 and end touches only
    w4 -- no reordering of the four solution words can form a second valid
    chain. That kills the largest class of ambiguity before distractors are
    even considered.
    """
    return any(graph.has_edge(nodes[i], nodes[j]) for i, j in chord_pairs(len(nodes)))


def edge_attributes(
    graph: nx.Graph, nodes: tuple[str, ...]
) -> tuple[tuple[float, ...], tuple[tuple[str, ...], ...]]:
    """Weights and relation tuples along the chain, in order."""
    weights, relations = [], []
    for a, b in zip(nodes, nodes[1:]):
        data = graph[a][b]
        weights.append(data["weight"])
        relations.append(tuple(data.get("relations", ())))
    return tuple(weights), tuple(relations)


# --------------------------------------------------------------------------
# The finder
# --------------------------------------------------------------------------


class BidirectionalBFSFinder:
    """Samples endpoint pairs, then meets in the middle between them.

    Endpoints are *sampled*, not supplied: nothing in the design requires
    particular start/end words, only a good chain. With mean degree ~14 a
    depth-2 frontier holds roughly 200 nodes, and two such frontiers in a
    7,600-node graph bridge readily -- so random pairs are productive rather
    than wasteful.
    """

    def __init__(
        self,
        graph: nx.Graph,
        cfg: Config,
        rng: random.Random,
        stemmer: Stemmer | None = None,
    ) -> None:
        self.graph = graph
        self.cfg = cfg
        self.rng = rng
        # Defaults to exact-match only. Callers that care about morphological
        # kin -- which is every real caller -- pass a Porter stemmer.
        self.stemmer = stemmer or _ExactStemmer()
        self.counts = FunnelCounts()
        # Sorted for reproducibility: sampling from a set would depend on hash
        # ordering, which varies between interpreter runs (planning.md 7.8).
        self.endpoints: tuple[str, ...] = tuple(
            sorted(n for n, d in graph.degree() if d >= cfg.min_endpoint_degree)
        )
        if len(self.endpoints) < 2:
            raise ValueError(
                f"only {len(self.endpoints)} nodes have degree >= "
                f"{cfg.min_endpoint_degree}; nothing to search between"
            )

    def sample_pair(self) -> tuple[str, str]:
        """Two distinct eligible endpoints."""
        a, b = self.rng.sample(self.endpoints, 2)
        return a, b

    # -- frontier ---------------------------------------------------------

    def _frontier(self, origin: str, routes_per_node: int = 2) -> dict[str, list[str]]:
        """Nodes at distance exactly 2 from `origin`, each with its via-nodes.

        Capped at `routes_per_node` intermediates per destination: extra
        routes to the same node produce near-identical puzzles, and we keep
        only one puzzle per endpoint pair anyway (planning.md 7.7.1).
        """
        out: dict[str, list[str]] = {}
        for via in sorted_neighbours(self.graph, origin, self.cfg.bfs_top_k):
            for dest in sorted_neighbours(self.graph, via, self.cfg.bfs_top_k):
                if dest == origin or dest == via:
                    continue
                routes = out.setdefault(dest, [])
                if len(routes) < routes_per_node:
                    routes.append(via)
        # Distance *exactly* 2: drop anything already adjacent to the origin.
        return {
            dest: vias
            for dest, vias in out.items()
            if not self.graph.has_edge(origin, dest)
        }

    # -- validation -------------------------------------------------------

    def _build(self, nodes: tuple[str, ...]) -> Path | None:
        """Apply every hard constraint. Returns None on any failure.

        Each early return attributes the rejection to the stage that caused
        it, which is what makes the funnel in `linkage diagnose` actionable.
        """
        c = self.counts
        c.paths_found += 1

        # A repeated node, or one that is merely the same word wearing a
        # different suffix. Both make the chain read as a trick.
        if has_stem_collision(self.stemmer, nodes):
            return None
        if has_direct_se_edge(self.graph, nodes):
            return None
        c.no_se_edge += 1

        if self.cfg.enforce_chordless and has_chord(self.graph, nodes):
            return None
        c.chordless += 1

        weights, relations = edge_attributes(self.graph, nodes)
        if min(weights) < self.cfg.min_edge_weight:
            return None
        c.weight_gate += 1

        return Path(
            start=nodes[0],
            end=nodes[-1],
            steps=nodes[1:-1],
            weights=weights,
            relations=relations,
        )

    # -- search -----------------------------------------------------------

    def paths_between(self, start: str, end: str) -> list[Path]:
        """Every valid chain between one endpoint pair, up to the budget.

        Bounded by `max_paths_per_pair` (Risk #20): the Phase 1 probe pulled
        33M paths from 25 seeds, so an unbounded search here would spend
        hours producing candidates nobody will review.
        """
        if start == end or self.graph.has_edge(start, end):
            return []

        forward = self._frontier(start)
        backward = self._frontier(end)
        if not forward or not backward:
            return []

        found: list[Path] = []
        for w2 in sorted(forward):
            for w3 in sorted_neighbours(self.graph, w2, self.cfg.bfs_top_k):
                if w3 not in backward:
                    continue
                for w1, w4 in itertools.product(forward[w2], backward[w3]):
                    path = self._build((start, w1, w2, w3, w4, end))
                    if path is not None:
                        found.append(path)
                        if len(found) >= self.cfg.max_paths_per_pair:
                            return found
        return found

    def find(self, budget: int) -> Iterator[Path]:
        """Yield valid chains from randomly sampled endpoint pairs.

        `budget` is the number of pairs to try, not paths to emit -- it is
        the unit of work we can actually bound in advance.
        """
        for _ in range(budget):
            start, end = self.sample_pair()
            self.counts.pairs_sampled += 1
            yield from self.paths_between(start, end)
