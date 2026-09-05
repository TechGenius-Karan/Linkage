"""Ranking candidates for human review (planning.md 7.6, 7.7).

Domain tier: pure.

Phase 1 measured yield at ~4.57M usable paths per 1,000 seeds against a
go/no-go threshold of 3. Finding paths is free. **Choosing** them is the whole
game now, which makes this file the one that decides whether Linkage is fun
(planning.md 7.9.6 -- the risk moved from #2 to #1).

This does not try to be a taste oracle. It orders the review queue so the
best candidates surface first; a person still makes every call.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from .models import Path

#: Weights per component. They sum to 1.0, so `quality` reads as 0..1.
#:
#: Retuned after reading the first 900 real candidates. Edge strength alone
#: put `SHARK -> ocean -> sailing -> fun -> dancing -> FATIGUE` at 0.91 and
#: `PROPOSITION -> statement -> answer -> reply -> echo -> REFLECTION` dead
#: last at 0.57 -- precisely backwards.
#:
#: The cause is the same trap as hub-degree in Phase 1: ConceptNet's edge
#: weight measures how *obvious* a link is, not how *good*. Vague, highly
#: connected words earn strong edges by co-occurring with everything. So
#: strength lost half its influence to `specificity`, which penalises exactly
#: those words.
COMPONENT_WEIGHTS: dict[str, float] = {
    "weakest_link": 0.20,
    "overall_strength": 0.10,
    "endpoint_distance": 0.20,
    "relation_variety": 0.15,
    "step_balance": 0.05,
    "specificity": 0.30,
}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass(frozen=True, slots=True)
class QualityScorer:
    """Scores a path 0..1, with the per-component breakdown kept.

    The breakdown is not decoration: when the review queue is full of bad
    puzzles, it is the only way to tell *which* component is mis-weighted.
    """

    #: Weight at which an edge counts as fully convincing. Phase 1 measured
    #: only 3.9% of edges above 3.0, so this is deliberately reachable.
    strong_edge: float = 4.0

    #: Degree at which a word counts as fully generic. The shipped graph has
    #: mean degree 14 and median 9; `animal` sits at 208 and the top-40 tail
    #: at ~95, so 100 marks the boundary where a word stops being a concept
    #: and starts being a category.
    hub_degree: float = 100.0

    def score(self, graph: nx.Graph, path: Path) -> tuple[float, tuple[tuple[str, float], ...]]:
        parts = {
            "weakest_link": self._weakest_link(path),
            "overall_strength": self._overall_strength(path),
            "endpoint_distance": self._endpoint_distance(graph, path),
            "relation_variety": self._relation_variety(path),
            "step_balance": self._step_balance(path),
            "specificity": self._specificity(graph, path),
        }
        total = sum(COMPONENT_WEIGHTS[k] * v for k, v in parts.items())
        breakdown = tuple(sorted(parts.items()))
        return round(total, 4), breakdown

    # -- components -------------------------------------------------------

    def _weakest_link(self, path: Path) -> float:
        """One weak rung is what makes a chain feel unfair, so the minimum
        edge carries the most weight of any single component."""
        return _clamp(path.min_weight / self.strong_edge)

    def _overall_strength(self, path: Path) -> float:
        """Geometric mean, not arithmetic: it punishes an outlier rung
        instead of letting one very strong edge mask four weak ones."""
        return _clamp(path.geometric_mean_weight / self.strong_edge)

    def _endpoint_distance(self, graph: nx.Graph, path: Path) -> float:
        """Start and end should feel unrelated.

        `apple -> ocean` is a puzzle; `apple -> fruit` is a definition. Shared
        neighbours are the cheap proxy for "these two are obviously related",
        and a direct edge is already banned by the pathfinder.
        """
        shared = len(set(graph[path.start]) & set(graph[path.end]))
        return _clamp(1.0 - shared / 8.0)

    def _relation_variety(self, path: Path) -> float:
        """A chain that is five RelatedTo hops reads as noise.

        Mixing IsA, AtLocation, UsedFor and Causes is what makes the leap feel
        like reasoning rather than co-occurrence.
        """
        kinds = {r for rels in path.relations for r in rels}
        return _clamp(len(kinds) / 5.0)

    def _specificity(self, graph: nx.Graph, path: Path) -> float:
        """Penalise chains routed through vague, highly connected words.

        This is the component that stops the scorer rewarding banality.
        `ocean -> sailing -> fun -> dancing` is four hubs in a row: every hop
        is "supported" by a strong edge and the chain still says nothing,
        because a word connected to everything connects two ideas only in the
        way that any two ideas are connected.

        Phase 1 taught this the expensive way with hub *pruning* -- degree is
        the wrong signal for deleting a word (`bird` is rich and popular), but
        it is a fair signal for suspecting a whole chain of vagueness when
        every rung is a hub.
        """
        degrees = [graph.degree(word) for word in path.steps]
        mean_degree = sum(degrees) / len(degrees)
        return _clamp(1.0 - mean_degree / self.hub_degree)

    def _step_balance(self, path: Path) -> float:
        """Penalise a chain whose edge weights swing wildly.

        A steady chain feels like a path; a lopsided one feels like one
        obvious hop plus four guesses.
        """
        span = max(path.weights) - min(path.weights)
        return _clamp(1.0 - span / (2.0 * self.strong_edge))
