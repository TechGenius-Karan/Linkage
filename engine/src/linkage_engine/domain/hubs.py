"""Hub-word detection (planning.md 7.3).

Domain tier: pure.

Words like `thing`, `person` and `use` have enormous degree in ConceptNet.
Left in, every shortest path routes through them and you get
`cat -> animal -> thing -> object -> box` -- technically valid, worthless.

This is the blunt half of the defence. `domain.wordlists.GENERIC_HUBS` is the
precise half, and planning.md 7.9.4 Tier 3 argues the curated list should
eventually carry most of the weight, because degree punishes a word for being
*well-connected* when the real problem is being *generic*.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import networkx as nx


def percentile(values: Sequence[int], p: float) -> int:
    """Nearest-rank percentile.

    Deliberately not interpolated: an integer degree cutoff is exactly what we
    want, and nearest-rank has no ambiguity about which convention was used --
    which matters because this value is recorded in graph metadata and must be
    reproducible.
    """
    if not values:
        raise ValueError("percentile of an empty sequence")
    if not 0.0 < p <= 100.0:
        raise ValueError(f"percentile must be in (0, 100], got {p}")
    ordered = sorted(values)
    rank = math.ceil(p / 100.0 * len(ordered))
    return ordered[max(1, rank) - 1]


def degree_cutoff(graph: nx.Graph, p: float) -> int:
    """Degree value at the p-th percentile of this graph's degree sequence."""
    return percentile([d for _, d in graph.degree()], p)


def find_hubs(graph: nx.Graph, p: float) -> tuple[set[str], int]:
    """Nodes whose degree is *strictly above* the p-th percentile.

    Returns `(hubs, cutoff)`. Strictly-above means a degenerate distribution
    where many nodes share the cutoff degree removes none of them, which is
    the safe direction -- we would rather keep a borderline word than
    silently gut the graph.
    """
    cutoff = degree_cutoff(graph, p)
    hubs = {n for n, d in graph.degree() if d > cutoff}
    return hubs, cutoff


def top_by_degree(graph: nx.Graph, n: int) -> list[tuple[str, int]]:
    """The `n` most-connected words, highest first, ties broken by name.

    This is the *useful* half of degree analysis. Automatic pruning on this
    signal deletes good puzzle words (Risk #19), but the same ranking is
    exactly the right shortlist to review by hand when deciding what belongs
    in `wordlists.GENERIC_HUBS`. Information, not automation.
    """
    return sorted(graph.degree(), key=lambda kv: (-kv[1], kv[0]))[:n]


def isolated_nodes(graph: nx.Graph) -> set[str]:
    """Nodes with no remaining edges -- useless for pathfinding."""
    return {n for n, d in graph.degree() if d == 0}


def sorted_neighbours(graph: nx.Graph, node: str, limit: int | None = None) -> list[str]:
    """Neighbours ordered by `(-weight, name)`, optionally truncated.

    Never iterate a networkx adjacency dict directly where the result affects
    output: dict order is insertion-dependent, which would silently break
    reproducibility (planning.md 7.8). Phase 2's pathfinder depends on this.
    """
    ranked = sorted(
        graph[node].items(),
        key=lambda kv: (-kv[1].get("weight", 0.0), kv[0]),
    )
    names = [n for n, _ in ranked]
    return names[:limit] if limit is not None else names


def degree_histogram(degrees: Iterable[int]) -> dict[str, int]:
    """Coarse buckets, for the build report."""
    buckets = {"1": 0, "2-5": 0, "6-20": 0, "21-100": 0, "101+": 0}
    for d in degrees:
        if d <= 1:
            buckets["1"] += 1
        elif d <= 5:
            buckets["2-5"] += 1
        elif d <= 20:
            buckets["6-20"] += 1
        elif d <= 100:
            buckets["21-100"] += 1
        else:
            buckets["101+"] += 1
    return buckets
