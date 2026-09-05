"""The uniqueness proof (planning.md 7.5).

If a puzzle has two valid arrangements, a player can be right and be told
they are wrong. That is not difficulty, it is a broken promise -- so this
file gets the most adversarial tests in the suite.
"""

from __future__ import annotations

import random
from itertools import permutations

import networkx as nx
import pytest

from linkage_engine.domain.validator import (
    chain_is_valid,
    count_solutions,
    is_uniquely_solvable,
    solve_all,
)


def chain(*words: str, weight: float = 2.0) -> nx.Graph:
    g = nx.Graph()
    for a, b in zip(words, words[1:]):
        g.add_edge(a, b, weight=weight)
    return g


# --------------------------------------------------------------------------
# chain_is_valid
# --------------------------------------------------------------------------


def test_valid_chain():
    g = chain("s", "a", "b", "c", "d", "e")
    assert chain_is_valid(g, "s", "e", ["a", "b", "c", "d"])


def test_chain_with_a_missing_link_is_invalid():
    g = chain("s", "a", "b", "c", "d", "e")
    g.remove_edge("b", "c")
    assert not chain_is_valid(g, "s", "e", ["a", "b", "c", "d"])


def test_chain_not_reaching_the_end_is_invalid():
    g = chain("s", "a", "b", "c", "d", "e")
    assert not chain_is_valid(g, "s", "zzz", ["a", "b", "c", "d"])


def test_empty_chain_is_invalid():
    assert not chain_is_valid(chain("s", "e"), "s", "e", [])


# --------------------------------------------------------------------------
# solve_all
# --------------------------------------------------------------------------


def test_finds_the_single_solution():
    g = chain("s", "a", "b", "c", "d", "e")
    assert solve_all(g, "s", "e", ["a", "b", "c", "d"]) == [("a", "b", "c", "d")]


def test_finds_both_when_a_puzzle_is_ambiguous():
    """The failure mode this whole module exists to catch."""
    g = chain("s", "a", "b", "c", "d", "e")
    # A second route of the same length through x and y.
    g.add_edge("s", "x", weight=2.0)
    g.add_edge("x", "y", weight=2.0)
    g.add_edge("y", "c", weight=2.0)
    solutions = solve_all(g, "s", "e", ["a", "b", "c", "d", "x", "y"])
    assert ("a", "b", "c", "d") in solutions
    assert ("x", "y", "c", "d") in solutions
    assert not is_uniquely_solvable(g, "s", "e", ["a", "b", "c", "d", "x", "y"])


def test_unsolvable_bank_returns_nothing():
    g = chain("s", "a", "b", "c", "d", "e")
    assert solve_all(g, "s", "e", ["a", "b", "c", "zzz"]) == []
    assert not is_uniquely_solvable(g, "s", "e", ["a", "b", "c", "zzz"])


def test_limit_stops_early():
    g = chain("s", "a", "b", "c", "d", "e")
    g.add_edge("s", "x", weight=2.0)
    g.add_edge("x", "y", weight=2.0)
    g.add_edge("y", "c", weight=2.0)
    bank = ["a", "b", "c", "d", "x", "y"]
    assert len(solve_all(g, "s", "e", bank, limit=1)) == 1
    assert len(solve_all(g, "s", "e", bank, limit=2)) == 2
    assert count_solutions(g, "s", "e", bank) >= 2


def test_duplicate_bank_entries_do_not_inflate_the_count():
    """A bank is a set of tiles. Passing a word twice must not create a
    phantom second solution and wrongly condemn a good puzzle."""
    g = chain("s", "a", "b", "c", "d", "e")
    assert is_uniquely_solvable(g, "s", "e", ["a", "b", "c", "d", "a", "b"])


def test_enumeration_order_is_deterministic():
    g = chain("s", "a", "b", "c", "d", "e")
    g.add_edge("s", "x", weight=2.0)
    g.add_edge("x", "y", weight=2.0)
    g.add_edge("y", "c", weight=2.0)
    forward = solve_all(g, "s", "e", ["a", "b", "c", "d", "x", "y"])
    backward = solve_all(g, "s", "e", ["y", "x", "d", "c", "b", "a"])
    assert forward == backward


# --------------------------------------------------------------------------
# Oracle: agreement with the plan's reference implementation
# --------------------------------------------------------------------------


def _reference_solve_all(g, start, end, bank, length=4):
    """planning.md 7.5 verbatim. The spec is the oracle."""
    return [
        p
        for p in permutations(sorted(bank), length)
        if g.has_edge(start, p[0])
        and all(g.has_edge(p[i], p[i + 1]) for i in range(length - 1))
        and g.has_edge(p[-1], end)
    ]


@pytest.mark.parametrize("trial", range(40))
def test_agrees_with_the_spec_reference_on_random_graphs(trial):
    """Fuzz against the plan's own code.

    Random Erdos-Renyi graphs produce ambiguous, unsolvable and uniquely
    solvable banks in roughly equal measure, which is exactly the mix worth
    fuzzing over.
    """
    rng = random.Random(trial)
    g = nx.gnp_random_graph(12, 0.35, seed=trial)
    g = nx.relabel_nodes(g, {i: f"w{i}" for i in g.nodes})
    nx.set_edge_attributes(g, 2.0, "weight")

    nodes = sorted(g.nodes)
    start, end = rng.sample(nodes, 2)
    bank = rng.sample([n for n in nodes if n not in (start, end)], 6)

    assert solve_all(g, start, end, bank) == _reference_solve_all(g, start, end, bank)
