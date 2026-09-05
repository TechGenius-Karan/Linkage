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

#: Wide enough that these unit tests exercise the cap, not the window.
#: Windowing itself is covered separately below.
WINDOW = 1000


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
            window=WINDOW,
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
        check(puzzles, max_word_reuse=3, window=WINDOW)


def test_word_at_exactly_the_cap_is_allowed():
    puzzles = [
        puzzle(i, f"s{i}", f"e{i}", [f"a{i}", f"b{i}", f"c{i}", "gravity"])
        for i in range(1, 4)
    ]
    assert check(puzzles, max_word_reuse=3, window=WINDOW).puzzles == 3


def test_duplicate_endpoint_pair_is_rejected():
    with pytest.raises(CorpusViolation, match="duplicate \\(start, end\\)"):
        check(
            [
                puzzle(1, "apple", "ocean", ["a", "b", "c", "d"]),
                puzzle(2, "apple", "ocean", ["e", "f", "g", "h"]),
            ],
            max_word_reuse=3,
            window=WINDOW,
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
            window=WINDOW,
        )


def test_repeated_solution_chain_is_rejected_even_with_new_endpoints():
    with pytest.raises(CorpusViolation, match="repeated solution chain"):
        check(
            [
                puzzle(1, "apple", "ocean", ["a", "b", "c", "d"]),
                puzzle(2, "piano", "forest", ["a", "b", "c", "d"]),
            ],
            max_word_reuse=9,
            window=WINDOW,
        )


def test_duplicate_ids_are_rejected():
    with pytest.raises(CorpusViolation, match="duplicate puzzle ids"):
        check(
            [
                puzzle(1, "a", "b", ["p", "q", "r", "s"]),
                puzzle(1, "c", "d", ["t", "u", "v", "w"]),
            ],
            max_word_reuse=3,
            window=WINDOW,
        )


def test_every_violation_is_reported_at_once():
    """One run should surface every problem, not make you fix them one by one."""
    puzzles = [
        puzzle(1, "apple", "ocean", ["a", "b", "c", "d"]),
        puzzle(2, "ocean", "apple", ["a", "b", "c", "d"]),
    ]
    with pytest.raises(CorpusViolation) as exc:
        check(puzzles, max_word_reuse=1, window=WINDOW)
    message = str(exc.value)
    assert "MAX_WORD_REUSE" in message
    assert "duplicate (start, end)" in message
    assert "repeated solution chain" in message


def test_empty_corpus_is_vacuously_clean():
    assert check([], max_word_reuse=3, window=WINDOW).puzzles == 0


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
    selected, _ = select_diverse(pool, target=20, max_word_reuse=3, window=WINDOW)
    puzzles = [
        Puzzle(i + 1, f"2026-10-{i + 1:02d}", c.path.start, c.path.end,
               c.path.steps, c.bank)
        for i, c in enumerate(selected)
    ]
    check(puzzles, max_word_reuse=3, window=WINDOW)  # must not raise


def test_selection_stops_at_the_reuse_cap():
    pool = [
        candidate(f"s{i}", f"e{i}", [f"a{i}", f"b{i}", f"c{i}", "gravity"])
        for i in range(10)
    ]
    selected, report = select_diverse(pool, target=10, max_word_reuse=3, window=WINDOW)
    assert len(selected) == 3
    assert report.skipped_word_cap == 7


def test_selection_skips_duplicate_endpoint_pairs():
    pool = [
        candidate("apple", "ocean", ["a", "b", "c", "d"]),
        candidate("ocean", "apple", ["e", "f", "g", "h"]),  # reversed
        candidate("piano", "forest", ["i", "j", "k", "l"]),
    ]
    selected, report = select_diverse(pool, target=10, max_word_reuse=9, window=WINDOW)
    assert len(selected) == 2
    assert report.skipped_duplicate_pair == 1


def test_selection_skips_repeated_chains():
    pool = [
        candidate("apple", "ocean", ["a", "b", "c", "d"]),
        candidate("piano", "forest", ["a", "b", "c", "d"]),
    ]
    selected, report = select_diverse(pool, target=10, max_word_reuse=9, window=WINDOW)
    assert len(selected) == 1
    assert report.skipped_duplicate_chain == 1


def test_selection_takes_the_best_candidate_that_fits():
    """Input is pre-sorted by preference, so the first fit is the best fit."""
    pool = [
        candidate("s1", "e1", ["a", "b", "c", "keep"], quality=0.9),
        candidate("s2", "e2", ["d", "e", "f", "keep"], quality=0.5),
    ]
    selected, _ = select_diverse(pool, target=1, max_word_reuse=1, window=WINDOW)
    assert selected[0].quality == 0.9


def test_selection_honours_the_target():
    pool = [candidate(f"s{i}", f"e{i}", [f"a{i}", f"b{i}", f"c{i}", f"d{i}"])
            for i in range(50)]
    selected, _ = select_diverse(pool, target=7, max_word_reuse=3, window=WINDOW)
    assert len(selected) == 7


def test_selection_counts_endpoints_against_the_cap():
    """`ocean` as a start word 20 times is as repetitive as in 20 banks."""
    pool = [
        candidate("ocean", f"e{i}", [f"a{i}", f"b{i}", f"c{i}", f"d{i}"])
        for i in range(10)
    ]
    selected, _ = select_diverse(pool, target=10, max_word_reuse=3, window=WINDOW)
    assert len(selected) == 3


def test_selection_of_an_empty_pool_is_empty():
    selected, report = select_diverse([], target=10, max_word_reuse=3, window=WINDOW)
    assert selected == [] and report.selected == 0


# --------------------------------------------------------------------------
# The rolling window -- reuse is seasonal, not a lifetime quota
# --------------------------------------------------------------------------


def test_a_word_becomes_available_again_once_it_leaves_the_window():
    """The point of windowing, exercised the way it is actually used.

    A lifetime cap retires a word forever, which is stricter than memory --
    nobody recalls a tile from five months ago. Across batches, the window
    slides and the word returns.
    """
    wants_river = [candidate("s9", "e9", ["p", "q", "r", "river"])]

    # Immediately after shipping `river`, with a cap of 1, it is blocked.
    just_used = [puzzle(1, "a1", "b1", ["x", "y", "z", "river"])]
    blocked, report = select_diverse(
        wants_river, target=1, max_word_reuse=1, window=3, already_shipped=just_used
    )
    assert blocked == []
    assert report.skipped_word_cap == 1

    # Two unrelated puzzles later it has fallen out of a 3-puzzle window.
    moved_on = just_used + [
        puzzle(2, "a2", "b2", ["d", "e", "f", "g"]),
        puzzle(3, "a3", "b3", ["h", "i", "j", "k"]),
    ]
    allowed, _ = select_diverse(
        wants_river, target=1, max_word_reuse=1, window=3, already_shipped=moved_on
    )
    assert len(allowed) == 1, "river never came back after leaving the window"


def test_window_of_one_imposes_no_constraint_between_puzzles():
    """A window of 1 means each puzzle only ever sees itself."""
    pool = [
        candidate(f"s{i}", f"e{i}", ["shared", "words", "every", f"time{i}"])
        for i in range(3)
    ]
    selected, _ = select_diverse(pool, target=3, max_word_reuse=1, window=1)
    assert len(selected) == 3


def test_check_uses_the_same_windowed_rule_as_selection():
    """If the two disagreed, a validly-built archive would fail its own
    check -- which is worse than either rule alone."""
    puzzles = [
        puzzle(i, f"s{i}", f"e{i}", [f"a{i}", f"b{i}", f"c{i}", "river"])
        for i in range(1, 7)
    ]
    # Six uses of `river`, cap 2 -- but spread across a window of 2 they are
    # never two-in-a-window... they are adjacent, so this must fail.
    with pytest.raises(CorpusViolation, match="within a 2-puzzle window"):
        check(puzzles, max_word_reuse=1, window=2)
    # Widen nothing but the cap and it passes.
    check(puzzles, max_word_reuse=6, window=2)


def test_check_ignores_uses_that_fell_out_of_the_window():
    early = puzzle(1, "s1", "e1", ["a", "b", "c", "river"])
    late = puzzle(9, "s9", "e9", ["p", "q", "r", "river"])
    filler = [
        puzzle(i, f"s{i}", f"e{i}", [f"w{i}", f"x{i}", f"y{i}", f"z{i}"])
        for i in range(2, 9)
    ]
    archive = [early, *filler, late]
    # Cap 1: the two `river` puzzles are 8 apart, so a window of 4 never
    # sees them together.
    check(archive, max_word_reuse=1, window=4)
    # A window wide enough to span both must complain.
    with pytest.raises(CorpusViolation, match="MAX_WORD_REUSE"):
        check(archive, max_word_reuse=1, window=20)


def test_check_reads_the_archive_in_puzzle_order():
    """Windowing is positional, so an out-of-order list must not change the
    verdict."""
    puzzles = [
        puzzle(i, f"s{i}", f"e{i}", [f"a{i}", f"b{i}", f"c{i}", "river"])
        for i in range(1, 4)
    ]
    forward = check(puzzles, max_word_reuse=3, window=10)
    backward = check(list(reversed(puzzles)), max_word_reuse=3, window=10)
    assert forward.puzzles == backward.puzzles


# --------------------------------------------------------------------------
# Incremental batches
# --------------------------------------------------------------------------


def test_selection_counts_words_already_shipped():
    """Month two must not quietly reuse month one's words -- the cap spans
    the archive, not the batch."""
    shipped = [puzzle(i, f"x{i}", f"y{i}", ["p", "q", "r", "gravity"]) for i in (1, 2, 3)]
    pool = [candidate(f"s{i}", f"e{i}", [f"a{i}", f"b{i}", f"c{i}", "gravity"])
            for i in range(5)]

    fresh, report = select_diverse(pool, target=5, max_word_reuse=3, window=WINDOW)
    assert len(fresh) == 3  # without history, three fit

    none_left, report = select_diverse(
        pool, target=5, max_word_reuse=3, window=WINDOW, already_shipped=shipped
    )
    assert none_left == []  # gravity is already at the cap
    assert report.skipped_word_cap == 5


def test_selection_will_not_repeat_a_shipped_endpoint_pair():
    shipped = [puzzle(1, "apple", "ocean", ["p", "q", "r", "s"])]
    pool = [candidate("ocean", "apple", ["a", "b", "c", "d"])]  # reversed
    selected, report = select_diverse(
        pool, target=5, max_word_reuse=9, window=WINDOW, already_shipped=shipped
    )
    assert selected == []
    assert report.skipped_duplicate_pair == 1


def test_selection_will_not_repeat_a_shipped_chain():
    shipped = [puzzle(1, "apple", "ocean", ["a", "b", "c", "d"])]
    pool = [candidate("piano", "forest", ["a", "b", "c", "d"])]
    selected, report = select_diverse(
        pool, target=5, max_word_reuse=9, window=WINDOW, already_shipped=shipped
    )
    assert selected == []
    assert report.skipped_duplicate_chain == 1


def test_batches_accumulate_into_an_archive_that_passes_check():
    """Three monthly batches in a row must still make a clean year."""
    pool = [
        candidate(f"s{i}", f"e{i}", [f"a{i}", f"b{i}", f"c{i}", f"d{i}"])
        for i in range(60)
    ]
    shipped: list[Puzzle] = []
    for _ in range(3):
        batch, _ = select_diverse(
            pool, target=5, max_word_reuse=3, window=WINDOW, already_shipped=shipped
        )
        assert len(batch) == 5
        start = len(shipped) + 1
        shipped += [
            Puzzle(start + n, f"2026-10-{start + n:02d}", c.path.start, c.path.end,
                   c.path.steps, c.bank)
            for n, c in enumerate(batch)
        ]
        # Candidates already used must not be offered again.
        chosen = {c.content_hash() for c in batch}
        pool = [c for c in pool if c.content_hash() not in chosen]

    assert len(shipped) == 15
    check(shipped, max_word_reuse=3, window=WINDOW)  # must not raise
