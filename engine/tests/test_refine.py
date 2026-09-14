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
from linkage_engine.domain import refine
from linkage_engine.domain.decisions import Puzzle
from linkage_engine.domain.distractors import SwapRefused, safe_swaps, swap_decoy
from linkage_engine.domain.models import Path
from linkage_engine.domain.pathfinder import has_chord
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


@pytest.fixture
def puzzle(bank):
    return Puzzle(start="s", end="e", solution=("w1", "w2", "w3", "w4"), bank=bank)


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


# --------------------------------------------------------------------------
# Suggestions for a flagged link, not just a decoy
# --------------------------------------------------------------------------


class TestSafeLinkFixes:
    def test_offers_only_words_the_engine_would_accept(self, graph, bank, puzzle):
        # `fix` connects both anchors of w2's slot -- a real candidate. Proof
        # mirrors `validate_puzzle`'s own two checks (chordless, unique) --
        # not the full function, since these fixture words ("s", "w1", ...)
        # are graph-search shorthand, not real 3-12-letter puzzle words.
        graph.add_edge("w1", "fix", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("fix", "w3", weight=2.5, relations=("RelatedTo",))
        options = refine.safe_link_fixes(CFG, graph, IdentityStemmer(), puzzle, bad_link=2)
        assert options
        for option in options:
            nodes = puzzle.nodes
            trial_nodes = nodes[: option.index + 1] + (option.word,) + nodes[option.index + 2 :]
            assert not has_chord(graph, trial_nodes)
            trial_bank = tuple(
                option.word if w == puzzle.solution[option.index] else w for w in bank
            )
            assert is_uniquely_solvable(graph, "s", "e", trial_bank, CFG.chain_length)

    def test_finds_the_common_neighbour_for_an_interior_link(self, graph, puzzle):
        graph.add_edge("w1", "fix", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("fix", "w3", weight=2.5, relations=("RelatedTo",))
        # Link 2 is w2 -> w3; it touches two rungs (w2 at index 1, w3 at
        # index 2), and only w2's slot has a real candidate here.
        options = refine.safe_link_fixes(CFG, graph, IdentityStemmer(), puzzle, bad_link=2)
        assert any(o.word == "fix" and o.index == 1 for o in options)

    def test_a_boundary_link_has_only_its_one_slot(self, graph, puzzle):
        # Link 0 is start -> w1: the start itself is not a candidate for this
        # feature, so only rung 0 (w1) can be offered a replacement.
        graph.add_edge("s", "opener", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("opener", "w2", weight=2.5, relations=("RelatedTo",))
        options = refine.safe_link_fixes(CFG, graph, IdentityStemmer(), puzzle, bad_link=0)
        assert any(o.word == "opener" and o.index == 0 for o in options)
        assert all(o.index == 0 for o in options)

    def test_never_offers_a_word_that_would_create_a_chord(self, graph, puzzle):
        graph.add_edge("w1", "fix", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("fix", "w3", weight=2.5, relations=("RelatedTo",))
        # `chordbait` is also a common neighbour of w1 and w3, but it also
        # touches w4 -- a straight shortcut across the chain the moment it
        # takes w2's slot.
        graph.add_edge("w1", "chordbait", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("chordbait", "w3", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("chordbait", "w4", weight=2.5, relations=("RelatedTo",))
        options = refine.safe_link_fixes(CFG, graph, IdentityStemmer(), puzzle, bad_link=2)
        assert "chordbait" not in {o.word for o in options}
        assert "fix" in {o.word for o in options}

    def test_never_offers_a_word_already_on_screen(self, graph, puzzle):
        # `dead2` is already a decoy in the bank; wiring it as a second
        # common neighbour of w1/w3 must not make it a suggestion.
        graph.add_edge("w1", "dead2", weight=2.5, relations=("RelatedTo",))
        options = refine.safe_link_fixes(CFG, graph, IdentityStemmer(), puzzle, bad_link=2)
        assert "dead2" not in {o.word for o in options}

    def test_honours_the_limit(self, graph, puzzle):
        graph.add_edge("w1", "fix", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("fix", "w3", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("w1", "fix2", weight=2.4, relations=("RelatedTo",))
        graph.add_edge("fix2", "w3", weight=2.4, relations=("RelatedTo",))
        options = refine.safe_link_fixes(
            CFG, graph, IdentityStemmer(), puzzle, bad_link=2, limit=1
        )
        assert len(options) <= 1

    def test_is_deterministic(self, graph, puzzle):
        graph.add_edge("w1", "fix", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("fix", "w3", weight=2.5, relations=("RelatedTo",))
        first = refine.safe_link_fixes(CFG, graph, IdentityStemmer(), puzzle, bad_link=2)
        second = refine.safe_link_fixes(CFG, graph, IdentityStemmer(), puzzle, bad_link=2)
        assert first == second

    def test_rejects_an_out_of_range_link(self, graph, puzzle):
        with pytest.raises(ValueError, match="0..4"):
            refine.safe_link_fixes(CFG, graph, IdentityStemmer(), puzzle, bad_link=5)


# --------------------------------------------------------------------------
# A joint fix for a whole span, not one word at a time
# --------------------------------------------------------------------------


class TestSafeRangeFixes:
    def test_offers_a_joint_two_word_replacement(self, graph, puzzle):
        # w1 -> a1 -> a2 -> w4 bridges the same two anchors a single-slot
        # search would use for w2 or w3 alone, but only as a pair.
        graph.add_edge("w1", "a1", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("a1", "a2", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("a2", "w4", weight=2.5, relations=("RelatedTo",))
        options = refine.safe_range_fixes(
            CFG, graph, IdentityStemmer(), puzzle, start_link=2, end_link=2
        )
        assert any(o.start_index == 1 and o.words == ("a1", "a2") for o in options)

    def test_offers_a_joint_three_word_replacement(self, graph, puzzle):
        graph.add_edge("s", "b1", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("b1", "b2", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("b2", "b3", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("b3", "w4", weight=2.5, relations=("RelatedTo",))
        options = refine.safe_range_fixes(
            CFG, graph, IdentityStemmer(), puzzle, start_link=1, end_link=2
        )
        assert any(o.start_index == 0 and o.words == ("b1", "b2", "b3") for o in options)

    def test_never_offers_a_combination_that_creates_a_chord(self, graph, puzzle):
        graph.add_edge("w1", "a1", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("a1", "a2", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("a2", "w4", weight=2.5, relations=("RelatedTo",))
        # A second bridging pair, but the far word also touches `e` directly
        # -- a shortcut the moment it takes over w3's slot.
        graph.add_edge("w1", "c1", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("c1", "c2", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("c2", "w4", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("c2", "e", weight=2.5, relations=("RelatedTo",))
        options = refine.safe_range_fixes(
            CFG, graph, IdentityStemmer(), puzzle, start_link=2, end_link=2
        )
        assert not any("c2" in o.words for o in options)
        assert any(o.words == ("a1", "a2") for o in options)

    def test_never_offers_a_word_already_on_screen(self, graph, puzzle):
        graph.add_edge("w1", "dead2", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("dead2", "a2", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("a2", "w4", weight=2.5, relations=("RelatedTo",))
        options = refine.safe_range_fixes(
            CFG, graph, IdentityStemmer(), puzzle, start_link=2, end_link=2
        )
        assert not any("dead2" in o.words for o in options)

    def test_rejects_a_span_wider_than_the_limit(self, graph, puzzle):
        with pytest.raises(ValueError, match="narrower span"):
            refine.safe_range_fixes(
                CFG, graph, IdentityStemmer(), puzzle, start_link=0, end_link=4
            )

    def test_rejects_start_after_end(self, graph, puzzle):
        with pytest.raises(ValueError, match="0..4"):
            refine.safe_range_fixes(
                CFG, graph, IdentityStemmer(), puzzle, start_link=3, end_link=1
            )

    def test_honours_the_limit(self, graph, puzzle):
        graph.add_edge("w1", "a1", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("a1", "a2", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("a2", "w4", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("w1", "d1", weight=2.4, relations=("RelatedTo",))
        graph.add_edge("d1", "d2", weight=2.4, relations=("RelatedTo",))
        graph.add_edge("d2", "w4", weight=2.4, relations=("RelatedTo",))
        options = refine.safe_range_fixes(
            CFG, graph, IdentityStemmer(), puzzle, start_link=2, end_link=2, limit=1
        )
        assert len(options) <= 1

    def test_is_deterministic(self, graph, puzzle):
        graph.add_edge("w1", "a1", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("a1", "a2", weight=2.5, relations=("RelatedTo",))
        graph.add_edge("a2", "w4", weight=2.5, relations=("RelatedTo",))
        first = refine.safe_range_fixes(
            CFG, graph, IdentityStemmer(), puzzle, start_link=2, end_link=2
        )
        second = refine.safe_range_fixes(
            CFG, graph, IdentityStemmer(), puzzle, start_link=2, end_link=2
        )
        assert first == second
