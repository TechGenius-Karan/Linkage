"""Corpus-level quality control (planning.md 7.7.1).

365 individually-good puzzles can still make a bad year. Nothing else in the
engine looks across puzzles, so these rules are the only thing standing
between us and shipping `gravity` forty times.
"""

from __future__ import annotations

import pytest

from linkage_engine.domain.corpus import (
    CorpusViolation,
    check,
    select_diverse,
    word_usage,
)
from linkage_engine.domain.models import Candidate, Path, Puzzle


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
    # 8 bank words plus 4 endpoints -- endpoints are on screen all game.
    assert report.distinct_words == 12


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


def test_word_usage_counts_endpoints_too():
    usage = word_usage(
        [
            puzzle(1, "ocean", "b", ["p", "q", "r", "s"]),
            puzzle(2, "c", "ocean", ["t", "u", "v", "w"]),
        ]
    )
    assert usage["ocean"] == 2


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


# --------------------------------------------------------------------------
# Diversity selection
# --------------------------------------------------------------------------


def candidate(start, end, steps, extra=(), quality=0.8) -> Candidate:
    steps = tuple(steps)
    path = Path(start, end, steps, (3.0,) * 5, (("RelatedTo",),) * 5)
    return Candidate(path=path, bank=tuple([*steps, *extra]), quality=quality)


def test_selection_output_always_passes_check():
    """The point of selecting by construction: the result cannot fail."""
    pool = [
        candidate(f"s{i}", f"e{i}", [f"a{i}", f"b{i}", "shared", "common"])
        for i in range(20)
    ]
    selected, _ = select_diverse(pool, target=20, max_word_reuse=3)
    puzzles = [
        Puzzle(i + 1, f"2026-10-{i + 1:02d}", c.path.start, c.path.end,
               c.path.steps, c.bank)
        for i, c in enumerate(selected)
    ]
    check(puzzles, max_word_reuse=3)  # must not raise


def test_selection_stops_at_the_reuse_cap():
    pool = [
        candidate(f"s{i}", f"e{i}", [f"a{i}", f"b{i}", f"c{i}", "gravity"])
        for i in range(10)
    ]
    selected, report = select_diverse(pool, target=10, max_word_reuse=3)
    assert len(selected) == 3
    assert report.skipped_word_cap == 7


def test_selection_skips_duplicate_endpoint_pairs():
    pool = [
        candidate("apple", "ocean", ["a", "b", "c", "d"]),
        candidate("ocean", "apple", ["e", "f", "g", "h"]),  # reversed
        candidate("piano", "forest", ["i", "j", "k", "l"]),
    ]
    selected, report = select_diverse(pool, target=10, max_word_reuse=9)
    assert len(selected) == 2
    assert report.skipped_duplicate_pair == 1


def test_selection_skips_repeated_chains():
    pool = [
        candidate("apple", "ocean", ["a", "b", "c", "d"]),
        candidate("piano", "forest", ["a", "b", "c", "d"]),
    ]
    selected, report = select_diverse(pool, target=10, max_word_reuse=9)
    assert len(selected) == 1
    assert report.skipped_duplicate_chain == 1


def test_selection_takes_the_best_candidate_that_fits():
    """Input is pre-sorted by preference, so the first fit is the best fit."""
    pool = [
        candidate("s1", "e1", ["a", "b", "c", "keep"], quality=0.9),
        candidate("s2", "e2", ["d", "e", "f", "keep"], quality=0.5),
    ]
    selected, _ = select_diverse(pool, target=1, max_word_reuse=1)
    assert selected[0].quality == 0.9


def test_selection_honours_the_target():
    pool = [candidate(f"s{i}", f"e{i}", [f"a{i}", f"b{i}", f"c{i}", f"d{i}"])
            for i in range(50)]
    selected, _ = select_diverse(pool, target=7, max_word_reuse=3)
    assert len(selected) == 7


def test_selection_counts_endpoints_against_the_cap():
    """`ocean` as a start word 20 times is as repetitive as in 20 banks."""
    pool = [
        candidate("ocean", f"e{i}", [f"a{i}", f"b{i}", f"c{i}", f"d{i}"])
        for i in range(10)
    ]
    selected, _ = select_diverse(pool, target=10, max_word_reuse=3)
    assert len(selected) == 3


def test_selection_of_an_empty_pool_is_empty():
    selected, report = select_diverse([], target=10, max_word_reuse=3)
    assert selected == [] and report.selected == 0
