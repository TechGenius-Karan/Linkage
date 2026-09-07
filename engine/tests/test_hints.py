"""Hint selection (planning.md 2.5.3)."""

from __future__ import annotations

import pytest

from linkage_engine.domain.hints import hint_words, obviousness
from linkage_engine.domain.models import Path


def make_path(weights: tuple[float, ...], steps: tuple[str, ...] = ("a", "b", "c", "d")) -> Path:
    return Path(
        start="start",
        end="end",
        steps=steps,
        weights=weights,
        relations=tuple(("IsA",) for _ in weights),
    )


class TestObviousness:
    def test_scores_each_slot_from_its_two_edges(self):
        # edges: start-a=2, a-b=4, b-c=6, c-d=8, d-end=10
        path = make_path((2.0, 4.0, 6.0, 8.0, 10.0))
        assert obviousness(path) == (3.0, 5.0, 7.0, 9.0)

    def test_one_weak_edge_drags_a_slot_down(self):
        # `b` sits between two strong edges; `a` hangs off a weak one.
        path = make_path((1.0, 9.0, 9.0, 5.0, 5.0))
        scores = obviousness(path)
        assert scores[1] > scores[0]

    def test_returns_one_score_per_slot(self):
        path = make_path((1.0, 2.0, 3.0, 4.0, 5.0))
        assert len(obviousness(path)) == len(path.steps)


class TestHintWords:
    def test_skips_the_most_obvious_word(self):
        # Slot scores: a=3, b=5, c=7, d=9  ->  ranked d, c, b, a.
        # The giveaway is `d`; hints are the next two.
        path = make_path((2.0, 4.0, 6.0, 8.0, 10.0))
        assert hint_words(path, 2) == ("c", "b")

    def test_never_offers_the_giveaway_even_as_a_third_hint(self):
        path = make_path((2.0, 4.0, 6.0, 8.0, 10.0))
        assert "d" not in hint_words(path, 3)

    def test_offers_the_hardest_rung_only_after_the_middle_ones(self):
        # The least obvious word usually carries the puzzle's "aha", so it must
        # not be the first thing a hint gives away.
        path = make_path((2.0, 4.0, 6.0, 8.0, 10.0))
        assert hint_words(path, 1) == ("c",)
        assert hint_words(path, 2)[0] == "c"

    def test_is_deterministic_across_calls(self):
        path = make_path((5.0, 5.0, 5.0, 5.0, 5.0))
        assert hint_words(path, 2) == hint_words(path, 2)

    def test_breaks_ties_by_word_not_by_position(self):
        # Every slot scores 5.0, so ordering falls to the tiebreak. Without one
        # the result would depend on dict/sort stability and could differ
        # between runs -- two players would then get different hints.
        path = make_path((5.0, 5.0, 5.0, 5.0, 5.0), steps=("delta", "alpha", "charlie", "bravo"))
        assert hint_words(path, 3) == ("bravo", "charlie", "delta")

    def test_hints_are_always_solution_words(self):
        path = make_path((3.0, 1.0, 4.0, 1.0, 5.0))
        assert set(hint_words(path, 2)) <= set(path.steps)

    def test_hints_are_distinct(self):
        path = make_path((3.0, 1.0, 4.0, 1.0, 5.0))
        hints = hint_words(path, 2)
        assert len(set(hints)) == len(hints)

    def test_asking_for_more_than_exist_yields_what_there_is(self):
        # Four slots minus the giveaway leaves three. Never pad by repeating --
        # a duplicated hint would spend a player's second hint on nothing.
        path = make_path((2.0, 4.0, 6.0, 8.0, 10.0))
        assert len(hint_words(path, 99)) == 3

    def test_zero_hints_is_empty(self):
        path = make_path((2.0, 4.0, 6.0, 8.0, 10.0))
        assert hint_words(path, 0) == ()

    def test_negative_count_is_rejected(self):
        path = make_path((2.0, 4.0, 6.0, 8.0, 10.0))
        with pytest.raises(ValueError):
            hint_words(path, -1)
