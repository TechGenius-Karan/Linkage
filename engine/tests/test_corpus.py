"""Corpus-level quality control (planning.md 7.7.1).

365 individually-good puzzles can still make a bad year. Nothing else in the
engine looks across puzzles, so these rules are the only thing standing
between us and shipping `gravity` forty times.
"""

from __future__ import annotations

import pytest

from linkage_engine.domain.corpus import CorpusViolation, check, word_usage
from linkage_engine.domain.models import Puzzle


def puzzle(pid: int, start: str, end: str, solution, extra=()) -> Puzzle:
    solution = tuple(solution)
    bank = tuple(sorted({*solution, *extra}))
    return Puzzle(
        id=pid,
        date=f"2026-10-{pid:02d}",
        start=start,
        end=end,
        solution=solution,
        bank=bank,
    )


def test_a_clean_corpus_passes():
    report = check(
        [
            puzzle(1, "apple", "ocean", ["newton", "gravity", "moon", "tide"]),
            puzzle(2, "piano", "forest", ["key", "lock", "wood", "oak"]),
        ],
        max_word_reuse=3,
    )
    assert report.puzzles == 2
    assert report.distinct_words == 8


def test_word_usage_counts_banks_not_just_solutions():
    """A word the player *sees* every other day feels repetitive whether or
    not it was ever the answer."""
    usage = word_usage(
        [
            puzzle(1, "a", "b", ["p", "q", "r", "s"], extra=["decoy"]),
            puzzle(2, "c", "d", ["t", "u", "v", "w"], extra=["decoy"]),
        ]
    )
    assert usage["decoy"] == 2


def test_overused_word_is_rejected():
    puzzles = [
        puzzle(i, f"s{i}", f"e{i}", [f"a{i}", f"b{i}", f"c{i}", "gravity"])
        for i in range(1, 6)
    ]
    with pytest.raises(CorpusViolation, match="MAX_WORD_REUSE"):
        check(puzzles, max_word_reuse=3)


def test_word_at_exactly_the_cap_is_allowed():
    puzzles = [
        puzzle(i, f"s{i}", f"e{i}", [f"a{i}", f"b{i}", f"c{i}", "gravity"])
        for i in range(1, 4)
    ]
    assert check(puzzles, max_word_reuse=3).puzzles == 3


def test_duplicate_endpoint_pair_is_rejected():
    with pytest.raises(CorpusViolation, match="duplicate \\(start, end\\)"):
        check(
            [
                puzzle(1, "apple", "ocean", ["a", "b", "c", "d"]),
                puzzle(2, "apple", "ocean", ["e", "f", "g", "h"]),
            ],
            max_word_reuse=3,
        )


def test_reversed_endpoint_pair_is_also_a_duplicate():
    """`APPLE -> OCEAN` and `OCEAN -> APPLE` are the same puzzle wearing a hat."""
    with pytest.raises(CorpusViolation, match="duplicate \\(start, end\\)"):
        check(
            [
                puzzle(1, "apple", "ocean", ["a", "b", "c", "d"]),
                puzzle(2, "ocean", "apple", ["e", "f", "g", "h"]),
            ],
            max_word_reuse=3,
        )


def test_repeated_solution_chain_is_rejected_even_with_new_endpoints():
    with pytest.raises(CorpusViolation, match="repeated solution chain"):
        check(
            [
                puzzle(1, "apple", "ocean", ["a", "b", "c", "d"]),
                puzzle(2, "piano", "forest", ["a", "b", "c", "d"]),
            ],
            max_word_reuse=9,
        )


def test_duplicate_ids_are_rejected():
    with pytest.raises(CorpusViolation, match="duplicate puzzle ids"):
        check(
            [
                puzzle(1, "a", "b", ["p", "q", "r", "s"]),
                puzzle(1, "c", "d", ["t", "u", "v", "w"]),
            ],
            max_word_reuse=3,
        )


def test_every_violation_is_reported_at_once():
    """One run should surface every problem, not make you fix them one by one."""
    puzzles = [
        puzzle(1, "apple", "ocean", ["a", "b", "c", "d"]),
        puzzle(2, "ocean", "apple", ["a", "b", "c", "d"]),
    ]
    with pytest.raises(CorpusViolation) as exc:
        check(puzzles, max_word_reuse=1)
    message = str(exc.value)
    assert "MAX_WORD_REUSE" in message
    assert "duplicate (start, end)" in message
    assert "repeated solution chain" in message


def test_empty_corpus_is_vacuously_clean():
    assert check([], max_word_reuse=3).puzzles == 0
