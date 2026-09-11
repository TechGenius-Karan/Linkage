"""Refining a bank by hand, and the engine's veto (planning.md 16.4).

The one rule worth stating plainly: a reviewer may soften a bank, and may not
break uniqueness -- not by accident, and not on purpose. Everything here is a
test of one half of that sentence.
"""

from __future__ import annotations

import networkx as nx
import pytest

from linkage_engine.config import Config
from linkage_engine.data.stemming import IdentityStemmer, PorterStemmerAdapter
from linkage_engine.domain.distractors import SwapRefused, safe_swaps, swap_decoy
from linkage_engine.domain.models import Path
from linkage_engine.domain.validator import is_uniquely_solvable

CFG = Config(bank_size=8, bank_size_min=6, distractor_pool_size=50)


@pytest.fixture
def graph():
    """A chain with dead ends hanging off it, plus one genuine shortcut.

        s - w1 - w2 - w3 - w4 - e     the solution
            |         |
          dead1     dead2             safe decoys: attached, but going nowhere

    `shortcut` is wired so that s - shortcut - w2 also works, which is exactly
    the shape that admits a second solution.
    """
    g = nx.Graph()
    nodes = ("s", "w1", "w2", "w3", "w4", "e")
    for a, b in zip(nodes, nodes[1:]):
        g.add_edge(a, b, weight=3.0, relations=("RelatedTo",))
    for anchor, decoy, weight in (
        ("w1", "dead1", 2.5),
        ("w3", "dead2", 2.0),
        ("w2", "dead3", 1.5),
        ("w4", "dead4", 1.0),
    ):
        g.add_edge(anchor, decoy, weight=weight, relations=("RelatedTo",))
    # An alternate opening: s -> shortcut -> w2 -> w3 -> w4 -> e is a second
    # valid arrangement the moment `shortcut` enters the bank.
    g.add_edge("s", "shortcut", weight=3.0, relations=("RelatedTo",))
    g.add_edge("shortcut", "w2", weight=3.0, relations=("RelatedTo",))
    return g


@pytest.fixture
def path(graph):
    nodes = ("s", "w1", "w2", "w3", "w4", "e")
    weights = tuple(graph[a][b]["weight"] for a, b in zip(nodes, nodes[1:]))
    relations = tuple(("RelatedTo",) for _ in weights)
    return Path("s", "e", nodes[1:-1], weights, relations)


@pytest.fixture
def bank():
    return ("dead1", "dead2", "w1", "w2", "w3", "w4")


def swap(graph, path, bank, removed, added, stemmer=None):
    return swap_decoy(CFG, graph, stemmer or IdentityStemmer(), path, bank, removed, added)


# --------------------------------------------------------------------------
# The veto
# --------------------------------------------------------------------------


class TestTheEngineRefuses:
    def test_a_swap_that_creates_a_second_solution(self, graph, path, bank):
        # The load-bearing case. `shortcut` gives s -> shortcut -> w2 -> w3 ->
        # w4 -> e, so the player could be right and be told they are wrong.
        with pytest.raises(SwapRefused, match="second valid solution"):
            swap(graph, path, bank, "dead1", "shortcut")

    def test_and_leaves_the_bank_untouched(self, graph, path, bank):
        with pytest.raises(SwapRefused):
            swap(graph, path, bank, "dead1", "shortcut")
        assert bank == ("dead1", "dead2", "w1", "w2", "w3", "w4")

    def test_removing_a_solution_word(self, graph, path, bank):
        # That would not refine the puzzle, it would delete it.
        with pytest.raises(SwapRefused, match="part of the solution"):
            swap(graph, path, bank, "w2", "dead3")

    def test_a_word_that_is_not_in_the_bank(self, graph, path, bank):
        with pytest.raises(SwapRefused, match="not in the bank"):
            swap(graph, path, bank, "absent", "dead3")

    def test_a_duplicate(self, graph, path, bank):
        with pytest.raises(SwapRefused, match="already in the bank"):
            swap(graph, path, bank, "dead1", "dead2")

    def test_a_word_already_on_the_ladder(self, graph, path, bank):
        with pytest.raises(SwapRefused, match="already in the puzzle"):
            swap(graph, path, bank, "dead1", "e")

    def test_a_word_the_graph_has_never_heard_of(self, graph, path, bank):
        # It could not ship as a tile: nothing proves it relates to anything.
        with pytest.raises(SwapRefused, match="not in the graph"):
            swap(graph, path, bank, "dead1", "qwertyuiop")

    def test_a_swap_that_changes_nothing(self, graph, path, bank):
        with pytest.raises(SwapRefused, match="changes nothing"):
            swap(graph, path, bank, "dead1", "dead1")

    def test_a_morphological_twin_of_a_word_already_on_screen(self, graph, path):
        # Every rule `build_bank` applies while choosing applies here too: a
        # bank edited by hand has to satisfy what a generated one does.
        graph.add_edge("w3", "moons", weight=2.0, relations=("RelatedTo",))
        graph.add_edge("w3", "moon", weight=2.0, relations=("RelatedTo",))
        with pytest.raises(SwapRefused, match="shares a stem"):
            swap_decoy(
                CFG,
                graph,
                PorterStemmerAdapter(),
                path,
                ("moon", "dead1", "w1", "w2", "w3", "w4"),
                "dead1",
                "moons",
            )

    def test_a_word_sitting_inside_another_word_on_screen(self, graph, path):
        graph.add_edge("w3", "sailing", weight=2.0, relations=("RelatedTo",))
        with pytest.raises(SwapRefused, match="contains, or sits inside"):
            swap(graph, path, ("sail", "dead1", "w1", "w2", "w3", "w4"), "dead1", "sailing")


# --------------------------------------------------------------------------
# The swap that works
# --------------------------------------------------------------------------


class TestTheEngineAllows:
    def test_a_safe_decoy_for_a_safe_decoy(self, graph, path, bank):
        assert swap(graph, path, bank, "dead1", "dead3") == (
            "dead2",
            "dead3",
            "w1",
            "w2",
            "w3",
            "w4",
        )

    def test_the_result_is_still_uniquely_solvable(self, graph, path, bank):
        after = swap(graph, path, bank, "dead1", "dead3")
        assert is_uniquely_solvable(graph, "s", "e", after, CFG.chain_length)

    def test_the_bank_keeps_its_size(self, graph, path, bank):
        assert len(swap(graph, path, bank, "dead1", "dead3")) == len(bank)

    def test_the_result_is_sorted(self, graph, path, bank):
        # A bank whose order depended on edit history would make the export
        # non-deterministic, which planning.md 7.8 forbids outright.
        after = swap(graph, path, bank, "dead1", "dead3")
        assert list(after) == sorted(after)

    def test_swaps_compose(self, graph, path, bank):
        once = swap(graph, path, bank, "dead1", "dead3")
        twice = swap(graph, path, once, "dead2", "dead4")
        assert set(twice) == {"dead3", "dead4", "w1", "w2", "w3", "w4"}


# --------------------------------------------------------------------------
# Suggestions
# --------------------------------------------------------------------------


class TestSafeSwaps:
    def test_offers_only_words_the_engine_would_accept(self, graph, path, bank):
        # A menu of options that get refused on click is worse than no menu.
        for option in safe_swaps(CFG, graph, IdentityStemmer(), path, bank, "dead1"):
            assert swap(graph, path, bank, "dead1", option.word)

    def test_never_offers_the_word_that_breaks_uniqueness(self, graph, path, bank):
        options = safe_swaps(CFG, graph, IdentityStemmer(), path, bank, "dead1")
        assert "shortcut" not in {o.word for o in options}

    def test_never_offers_something_already_in_the_bank(self, graph, path, bank):
        options = safe_swaps(CFG, graph, IdentityStemmer(), path, bank, "dead1")
        assert not {o.word for o in options} & set(bank)

    def test_carries_the_temptingness_so_softening_is_a_visible_move(
        self, graph, path, bank
    ):
        # Round 1's finding was that banks were uniformly too hard. A reviewer
        # cannot act on that without seeing which way a swap moves the bank.
        options = safe_swaps(CFG, graph, IdentityStemmer(), path, bank, "dead1")
        assert options
        assert all(o.temptingness > 0 for o in options)
        assert all(o.source for o in options)

    def test_honours_the_limit(self, graph, path, bank):
        assert len(safe_swaps(CFG, graph, IdentityStemmer(), path, bank, "dead1", limit=1)) <= 1

    def test_is_deterministic(self, graph, path, bank):
        first = safe_swaps(CFG, graph, IdentityStemmer(), path, bank, "dead1")
        assert first == safe_swaps(CFG, graph, IdentityStemmer(), path, bank, "dead1")
