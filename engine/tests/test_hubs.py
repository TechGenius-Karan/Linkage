"""Percentile arithmetic and deterministic neighbour ordering."""

from __future__ import annotations

import networkx as nx
import pytest

from linkage_engine.domain.hubs import (
    degree_cutoff,
    degree_histogram,
    find_hubs,
    isolated_nodes,
    percentile,
    sorted_neighbours,
)


@pytest.mark.parametrize(
    "values, p, expected",
    [
        ([1, 2, 3, 4, 5], 100, 5),
        ([1, 2, 3, 4, 5], 50, 3),
        (list(range(1, 101)), 99, 99),
        (list(range(1, 101)), 1, 1),
        ([7], 99, 7),
        ([5, 1, 3], 50, 3),  # unsorted input
    ],
)
def test_percentile_nearest_rank(values, p, expected):
    assert percentile(values, p) == expected


def test_percentile_rejects_empty_input():
    with pytest.raises(ValueError, match="empty"):
        percentile([], 99)


@pytest.mark.parametrize("p", [0, -1, 101, 200])
def test_percentile_rejects_out_of_range(p):
    with pytest.raises(ValueError, match="must be in"):
        percentile([1, 2, 3], p)


def test_find_hubs_is_strictly_greater_than_the_cutoff():
    g = nx.Graph()
    for i in range(99):
        g.add_edge("hub", f"n{i}")
    hubs, cutoff = find_hubs(g, 99.0)
    assert hubs == {"hub"}
    assert cutoff == 1


def test_find_hubs_removes_nothing_from_a_regular_graph():
    g = nx.cycle_graph(20)
    hubs, cutoff = find_hubs(g, 99.0)
    assert hubs == set()
    assert cutoff == 2


def test_degree_cutoff_matches_percentile_of_the_degree_sequence():
    g = nx.star_graph(10)  # centre degree 10, leaves degree 1
    assert degree_cutoff(g, 100.0) == 10
    assert degree_cutoff(g, 50.0) == 1


def test_isolated_nodes():
    g = nx.Graph()
    g.add_edge("a", "b")
    g.add_node("lonely")
    assert isolated_nodes(g) == {"lonely"}


def test_sorted_neighbours_orders_by_weight_then_name():
    g = nx.Graph()
    g.add_edge("x", "low", weight=1.0)
    g.add_edge("x", "high", weight=9.0)
    g.add_edge("x", "beta", weight=5.0)
    g.add_edge("x", "alpha", weight=5.0)  # tie with beta -> name breaks it

    assert sorted_neighbours(g, "x") == ["high", "alpha", "beta", "low"]


def test_sorted_neighbours_respects_the_limit():
    g = nx.Graph()
    for i in range(10):
        g.add_edge("x", f"n{i}", weight=float(i))
    assert sorted_neighbours(g, "x", limit=3) == ["n9", "n8", "n7"]


def test_sorted_neighbours_is_stable_across_insertion_orders():
    """Reproducibility (planning.md 7.8): dict order must never leak into
    output. Phase 2's pathfinder depends on this holding."""
    forward = nx.Graph()
    backward = nx.Graph()
    edges = [("x", "a", 3.0), ("x", "b", 1.0), ("x", "c", 2.0)]
    for u, v, w in edges:
        forward.add_edge(u, v, weight=w)
    for u, v, w in reversed(edges):
        backward.add_edge(u, v, weight=w)

    assert sorted_neighbours(forward, "x") == sorted_neighbours(backward, "x")


def test_sorted_neighbours_tolerates_a_missing_weight():
    g = nx.Graph()
    g.add_edge("x", "unweighted")
    g.add_edge("x", "weighted", weight=1.0)
    assert sorted_neighbours(g, "x") == ["weighted", "unweighted"]


def test_degree_histogram_buckets():
    assert degree_histogram([1, 1, 3, 10, 50, 500]) == {
        "1": 2,
        "2-5": 1,
        "6-20": 1,
        "21-100": 1,
        "101+": 1,
    }
