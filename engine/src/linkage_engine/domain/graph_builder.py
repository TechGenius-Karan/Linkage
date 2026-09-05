"""Assemble a concept graph from filtered assertions (planning.md 7.2).

Domain tier: no I/O, no network, no filesystem. networkx is an in-memory data
structure, not an external boundary, so using it here is fine.

The transformation functions mutate the graph in place and return a report of
what they removed. Copying a graph with a million edges to preserve purity
would cost more than it buys; the mutation is local, documented, and each
function has exactly one job.
"""

from __future__ import annotations

import statistics
from typing import Iterable

import networkx as nx

from .hubs import find_hubs, isolated_nodes
from .models import Assertion, GraphStats


def build(
    assertions: Iterable[Assertion],
    vocabulary: frozenset[str],
    min_weight: float,
) -> nx.Graph:
    """Fold assertions into an undirected weighted graph.

    Rejects, in order: self-loops, endpoints outside the vocabulary, and edges
    below `min_weight`.

    When the same word pair arrives via several relations, the edge keeps the
    **maximum** weight seen and the **union** of relations -- a pair asserted
    by two independent relations is better evidence, not worse.
    """
    graph = nx.Graph()
    relations: dict[tuple[str, str], set[str]] = {}

    for a in assertions:
        if a.start == a.end:
            continue
        if a.start not in vocabulary or a.end not in vocabulary:
            continue
        if a.weight < min_weight:
            continue

        key = (a.start, a.end) if a.start < a.end else (a.end, a.start)
        existing = graph.get_edge_data(a.start, a.end)
        if existing is None:
            graph.add_edge(a.start, a.end, weight=a.weight)
            relations[key] = {a.relation}
        else:
            if a.weight > existing["weight"]:
                existing["weight"] = a.weight
            relations[key].add(a.relation)

    # Freeze relation sets into sorted tuples: immutable, and deterministically
    # ordered so the pickled artifact is byte-stable (planning.md 7.8).
    for (u, v), rels in relations.items():
        graph[u][v]["relations"] = tuple(sorted(rels))

    return graph


def prune_hubs(graph: nx.Graph, percentile: float) -> tuple[set[str], int]:
    """Remove nodes above the degree percentile. Mutates `graph`.

    Returns `(removed, cutoff)`.
    """
    hubs, cutoff = find_hubs(graph, percentile)
    graph.remove_nodes_from(hubs)
    return hubs, cutoff


def drop_isolated(graph: nx.Graph) -> set[str]:
    """Remove nodes left with no edges. Mutates `graph`.

    Hub removal disconnects things: in a scale-free graph the top 1% of nodes
    can carry 20-30% of all edges (planning.md 7.9.1), so this always has work
    to do after `prune_hubs`.
    """
    orphans = isolated_nodes(graph)
    graph.remove_nodes_from(orphans)
    return orphans


def summarise(
    graph: nx.Graph,
    *,
    hubs_removed: int,
    isolated_removed: int,
    hub_degree_cutoff: int,
) -> GraphStats:
    """Shape of the finished graph, for the build report and sanity checks."""
    degrees = [d for _, d in graph.degree()]
    return GraphStats(
        nodes=graph.number_of_nodes(),
        edges=graph.number_of_edges(),
        isolated_removed=isolated_removed,
        hubs_removed=hubs_removed,
        hub_degree_cutoff=hub_degree_cutoff,
        mean_degree=round(statistics.fmean(degrees), 2) if degrees else 0.0,
        median_degree=int(statistics.median(degrees)) if degrees else 0,
        max_degree=max(degrees) if degrees else 0,
    )
