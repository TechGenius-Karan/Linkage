"""Corpus-level quality control (planning.md 7.7.1).

Domain tier: pure.

Every other check in this engine validates a puzzle **in isolation**. A set of
365 individually-good puzzles can still be a bad *year*, and nothing else
would catch it: `gravity` in forty banks, `APPLE -> OCEAN` shipping twice in
opposite directions, the same chain under different endpoints.

These run at export and **fail loudly**. Shipping a bad year quietly is the
one outcome worth crashing over.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from .models import Puzzle


class CorpusViolation(Exception):
    """Raised when the assembled archive breaks a corpus-level rule."""


@dataclass(frozen=True, slots=True)
class CorpusReport:
    puzzles: int
    distinct_words: int
    most_reused: tuple[tuple[str, int], ...]

    def summary(self) -> str:
        return f"{self.puzzles} puzzles, {self.distinct_words} distinct words"


def word_usage(puzzles: Sequence[Puzzle]) -> Counter[str]:
    """How often each word appears in any bank.

    Counts **bank** appearances, not just solutions: a word the player sees
    every other day feels repetitive whether or not it was the answer.
    """
    usage: Counter[str] = Counter()
    for puzzle in puzzles:
        usage.update(set(puzzle.bank))
    return usage


def check(puzzles: Sequence[Puzzle], max_word_reuse: int) -> CorpusReport:
    """Validate the whole archive. Raises `CorpusViolation` on any breach."""
    problems: list[str] = []

    # -- word repetition ---------------------------------------------------
    usage = word_usage(puzzles)
    overused = sorted(
        ((w, n) for w, n in usage.items() if n > max_word_reuse),
        key=lambda kv: (-kv[1], kv[0]),
    )
    if overused:
        shown = ", ".join(f"{w} x{n}" for w, n in overused[:10])
        problems.append(
            f"{len(overused)} word(s) exceed MAX_WORD_REUSE={max_word_reuse}: {shown}"
        )

    # -- duplicate endpoint pairs, in either direction ---------------------
    pairs: dict[frozenset[str], list[int]] = {}
    for puzzle in puzzles:
        pairs.setdefault(frozenset({puzzle.start, puzzle.end}), []).append(puzzle.id)
    dupes = {pair: ids for pair, ids in pairs.items() if len(ids) > 1}
    if dupes:
        shown = "; ".join(
            f"{'/'.join(sorted(pair))} in puzzles {ids}" for pair, ids in list(dupes.items())[:5]
        )
        problems.append(f"{len(dupes)} duplicate (start, end) pair(s): {shown}")

    # -- repeated solution chains -----------------------------------------
    chains: dict[tuple[str, ...], list[int]] = {}
    for puzzle in puzzles:
        chains.setdefault(puzzle.solution, []).append(puzzle.id)
    repeated = {c: ids for c, ids in chains.items() if len(ids) > 1}
    if repeated:
        shown = "; ".join(
            f"{' -> '.join(c)} in {ids}" for c, ids in list(repeated.items())[:5]
        )
        problems.append(f"{len(repeated)} repeated solution chain(s): {shown}")

    # -- per-puzzle sanity that only shows up in aggregate -----------------
    ids = [p.id for p in puzzles]
    if len(set(ids)) != len(ids):
        problems.append("duplicate puzzle ids")
    dates = [p.date for p in puzzles]
    if len(set(dates)) != len(dates):
        problems.append("duplicate puzzle dates")

    if problems:
        raise CorpusViolation(
            "corpus-level quality control failed:\n  - " + "\n  - ".join(problems)
        )

    return CorpusReport(
        puzzles=len(puzzles),
        distinct_words=len(usage),
        most_reused=tuple(usage.most_common(10)),
    )
