"""The uniqueness proof (planning.md 7.5).

Domain tier: pure.

This is the one property the entire game rests on. If a puzzle has two valid
arrangements, a player can be correct and be told they are wrong -- which is
not a difficulty problem, it is a broken promise.

    P(11, 4) = 7,920 arrangements x 5 hash lookups per check.

`itertools.permutations` is correct, obvious at 3am, and fast enough. The
incremental bank construction in `distractors.py` calls this once per
candidate distractor -- roughly 57k permutations per puzzle in total, about
60ms. A hand-rolled pruned DFS would be faster and would earn its keep only
if that ever became the bottleneck. It is not.
"""

from __future__ import annotations

from itertools import permutations
from typing import Iterable, Sequence

import networkx as nx


def chain_is_valid(
    graph: nx.Graph, start: str, end: str, chain: Sequence[str]
) -> bool:
    """True when `start -> chain... -> end` is an unbroken run of edges."""
    if not chain:
        return False
    if not graph.has_edge(start, chain[0]):
        return False
    for a, b in zip(chain, chain[1:]):
        if not graph.has_edge(a, b):
            return False
    return graph.has_edge(chain[-1], end)


def solve_all(
    graph: nx.Graph,
    start: str,
    end: str,
    bank: Iterable[str],
    length: int = 4,
    limit: int | None = None,
) -> list[tuple[str, ...]]:
    """Every ordered arrangement of `bank` words forming a valid chain.

    `sorted(bank)` makes the enumeration order deterministic, so a failure
    report names the same alternate solution on every run.

    `limit` stops early. Callers that only need to know "is there more than
    one?" pass `limit=2` -- there is no reason to enumerate all 7,920 when
    the second hit already settles it.
    """
    found: list[tuple[str, ...]] = []
    for arrangement in permutations(sorted(set(bank)), length):
        if chain_is_valid(graph, start, end, arrangement):
            found.append(arrangement)
            if limit is not None and len(found) >= limit:
                break
    return found


def is_uniquely_solvable(
    graph: nx.Graph, start: str, end: str, bank: Iterable[str], length: int = 4
) -> bool:
    """Exactly one valid arrangement exists."""
    return len(solve_all(graph, start, end, bank, length, limit=2)) == 1


def count_solutions(
    graph: nx.Graph, start: str, end: str, bank: Iterable[str], length: int = 4
) -> int:
    """Full count. Used by reporting and the golden test, never on a hot path."""
    return len(solve_all(graph, start, end, bank, length))
