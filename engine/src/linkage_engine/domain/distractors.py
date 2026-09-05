"""Red herrings, and the bank they build (planning.md 7.6).

Domain tier: pure.

A distractor's job is to be *tempting*, not merely wrong. A word nobody would
ever pick adds difficulty of zero while occupying a tile.

The bank is built **incrementally**, admitting a candidate only if the bank
stays uniquely solvable. Uniqueness therefore becomes an invariant of the
construction rather than a property we generate-and-hope for. The golden test
re-proves it independently on the shipped output -- belt and braces, because
this is the one property the whole game rests on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import networkx as nx

from ..config import Config
from .models import Path
from .ports import Stemmer
from .validator import is_uniquely_solvable


@dataclass(frozen=True, slots=True)
class ScoredWord:
    word: str
    temptingness: float
    source: str  # which strategy proposed it; shown during review


class DistractorStrategy(Protocol):
    """Proposes candidate red herrings for one path.

    This is the one place the engine genuinely expects new behaviour without
    modifying existing code (planning.md 5, Open/Closed). Three real
    implementations exist from day one, so the abstraction is earned rather
    than speculative; a fourth is a new class plus one registry entry.
    """

    name: str

    def propose(self, graph: nx.Graph, path: Path, k: int) -> list[ScoredWord]: ...


# --------------------------------------------------------------------------
# Strategies
# --------------------------------------------------------------------------


def _edge_weight(graph: nx.Graph, a: str, b: str) -> float:
    data = graph.get_edge_data(a, b)
    return data["weight"] if data else 0.0


class NearMissStrategy:
    """One hop from a solution word, but a dead end.

    Feels adjacent to the answer because it *is* adjacent -- which is exactly
    why it tempts. These are also the most likely to be refused by the
    uniqueness check, for the same reason.
    """

    name = "near-miss"

    def propose(self, graph: nx.Graph, path: Path, k: int) -> list[ScoredWord]:
        on_path = set(path.nodes)
        scored: dict[str, float] = {}
        for step in path.steps:
            for neighbour in graph[step]:
                if neighbour in on_path:
                    continue
                weight = _edge_weight(graph, step, neighbour)
                if weight > scored.get(neighbour, 0.0):
                    scored[neighbour] = weight
        return _rank(scored, self.name, k)


class SiblingStrategy:
    """Shares an `IsA` parent with a solution word: right category, wrong member.

    `robin` beside `sparrow` when the answer is `eagle` -- the player has the
    category correct and still has to choose.
    """

    name = "sibling"

    def propose(self, graph: nx.Graph, path: Path, k: int) -> list[ScoredWord]:
        on_path = set(path.nodes)
        scored: dict[str, float] = {}
        for step in path.steps:
            for parent, data in graph[step].items():
                if "IsA" not in data.get("relations", ()):
                    continue
                for sibling, sib_data in graph[parent].items():
                    if sibling in on_path or sibling == parent:
                        continue
                    if "IsA" not in sib_data.get("relations", ()):
                        continue
                    weight = min(data["weight"], sib_data["weight"])
                    if weight > scored.get(sibling, 0.0):
                        scored[sibling] = weight
        return _rank(scored, self.name, k)


class SemanticFieldStrategy:
    """Close to start or end, disconnected from the chain interior.

    Looks like an obvious opening or closing move, and goes nowhere. Excluded
    explicitly if it touches an interior word, since that would make it a
    near-miss instead and double-count the same idea.
    """

    name = "semantic-field"

    def propose(self, graph: nx.Graph, path: Path, k: int) -> list[ScoredWord]:
        on_path = set(path.nodes)
        interior = set(path.steps)
        scored: dict[str, float] = {}
        for anchor in (path.start, path.end):
            for neighbour in graph[anchor]:
                if neighbour in on_path:
                    continue
                if any(graph.has_edge(neighbour, w) for w in interior):
                    continue
                weight = _edge_weight(graph, anchor, neighbour)
                if weight > scored.get(neighbour, 0.0):
                    scored[neighbour] = weight
        return _rank(scored, self.name, k)


def _rank(scored: dict[str, float], source: str, k: int) -> list[ScoredWord]:
    """Highest temptingness first, ties broken by name for reproducibility."""
    ordered = sorted(scored.items(), key=lambda kv: (-kv[1], kv[0]))
    return [ScoredWord(w, s, source) for w, s in ordered[:k]]


DEFAULT_STRATEGIES: tuple[DistractorStrategy, ...] = (
    NearMissStrategy(),
    SiblingStrategy(),
    SemanticFieldStrategy(),
)


# --------------------------------------------------------------------------
# Bank-level rejections (planning.md 7.6)
# --------------------------------------------------------------------------


def shares_stem(stemmer: Stemmer, word: str, existing: frozenset[str]) -> bool:
    """`moon` beside `moons`, `sail` beside `sailing`.

    The FormOf/DerivedFrom relation blocklist keeps these out of the graph's
    *edges*, but nothing stops both landing in the same *bank*.
    """
    stem = stemmer.stem(word)
    return any(stemmer.stem(other) == stem for other in existing)


def overlaps_substring(word: str, existing: frozenset[str], min_len: int = 4) -> bool:
    """One bank word contained in another, where the shorter is >= `min_len`.

    Catches compounds the stemmer misses. `art` inside `heart` is fine and
    stays -- three letters is short enough to be coincidence rather than
    something a player would read as a hint.
    """
    for other in existing:
        short, long = sorted((word, other), key=len)
        if len(short) >= min_len and short in long:
            return True
    return False


# --------------------------------------------------------------------------
# The selector
# --------------------------------------------------------------------------


class DistractorSelector:
    """Builds a word bank that is uniquely solvable by construction."""

    def __init__(
        self,
        cfg: Config,
        stemmer: Stemmer,
        strategies: tuple[DistractorStrategy, ...] = DEFAULT_STRATEGIES,
    ) -> None:
        self.cfg = cfg
        self.stemmer = stemmer
        self.strategies = strategies

    def pool(self, graph: nx.Graph, path: Path) -> list[ScoredWord]:
        """Merged, ranked candidate pool across every strategy.

        A word proposed by several strategies keeps its highest temptingness
        and the name of the strategy that scored it that way.
        """
        best: dict[str, ScoredWord] = {}
        for strategy in self.strategies:
            for candidate in strategy.propose(graph, path, self.cfg.distractor_pool_size):
                incumbent = best.get(candidate.word)
                if incumbent is None or candidate.temptingness > incumbent.temptingness:
                    best[candidate.word] = candidate
        return sorted(best.values(), key=lambda s: (-s.temptingness, s.word))

    def consideration_order(self, pool: list[ScoredWord]) -> list[ScoredWord]:
        """Interleave the ranked pool across temptingness bands.

        The pool arrives sorted hardest-first, and taking the top slice
        outright produced banks where every single tile was a near-miss --
        measured at 95% of decoys wired to one side of a solution slot, with
        no difference between puzzles reviewers liked and ones they rejected.
        It was not a quality signal; it was every bank.

        Uniqueness guarantees no decoy *actually* fits, but a player cannot
        see that. A tile attached to one side of a slot looks like it belongs
        there and costs a life to disprove. Spreading the draw across hard,
        medium and easy bands gives a bank texture: some tiles can be
        dismissed on sight, which is what makes the genuinely hard ones feel
        fair rather than arbitrary.
        """
        if len(pool) < 6:
            return list(pool)

        third = len(pool) // 3
        bands = [pool[:third], pool[third : 2 * third], pool[2 * third :]]
        take = self.cfg.distractor_mix
        cursors = [0, 0, 0]
        order: list[ScoredWord] = []

        while any(cursors[i] < len(bands[i]) for i in range(3)):
            for band in range(3):
                for _ in range(take[band]):
                    if cursors[band] < len(bands[band]):
                        order.append(bands[band][cursors[band]])
                        cursors[band] += 1
        return order

    def build_bank(self, graph: nx.Graph, path: Path) -> tuple[str, ...] | None:
        """Solution words plus the most tempting *safe* distractors.

        Returns None when too few safe distractors exist to reach
        `bank_size_min` -- the candidate is then dropped rather than shipped
        with a thin bank (Risk #16).
        """
        solution = frozenset(path.steps)
        bank: set[str] = set(solution)
        forbidden = set(path.nodes)

        for candidate in self.consideration_order(self.pool(graph, path)):
            if len(bank) >= self.cfg.bank_size:
                break
            word = candidate.word
            if word in forbidden or word in bank:
                continue
            # Compare against the endpoints too, not just the bank. A decoy
            # `branch` under an end word of `branches` is exactly as sloppy as
            # `moon` beside `moons`, and the endpoints are on screen the whole
            # time -- so it is the more visible of the two.
            frozen = frozenset(bank | {path.start, path.end})
            if shares_stem(self.stemmer, word, frozen):
                continue
            if overlaps_substring(word, frozen):
                continue
            # The load-bearing check: admit only if uniqueness survives.
            if not is_uniquely_solvable(
                graph, path.start, path.end, bank | {word}, self.cfg.chain_length
            ):
                continue
            bank.add(word)

        if len(bank) < self.cfg.bank_size_min:
            return None
        return tuple(sorted(bank))
