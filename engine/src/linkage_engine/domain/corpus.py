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

from .models import Candidate, Puzzle


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
    """How often each word appears anywhere a player can see it.

    Counts the **bank and both endpoints**, not just solutions. A word the
    player looks at every other day feels repetitive whether or not it was
    the answer -- and the start and end words sit on screen for the entire
    game, so they are the most visible of all.
    """
    usage: Counter[str] = Counter()
    for puzzle in puzzles:
        usage.update({*puzzle.bank, puzzle.start, puzzle.end})
    return usage


@dataclass(frozen=True, slots=True)
class SelectionReport:
    considered: int
    selected: int
    skipped_word_cap: int
    skipped_duplicate_pair: int
    skipped_duplicate_chain: int

    def summary(self) -> str:
        return (
            f"selected {self.selected} of {self.considered} "
            f"(skipped {self.skipped_word_cap} word-cap, "
            f"{self.skipped_duplicate_pair} dup-pair, "
            f"{self.skipped_duplicate_chain} dup-chain)"
        )


def select_diverse(
    candidates: Sequence[Candidate],
    *,
    target: int,
    max_word_reuse: int,
    already_shipped: Sequence[Puzzle] = (),
) -> tuple[list[Candidate], SelectionReport]:
    """Greedily pick a subset that satisfies the corpus rules by construction.

    `check` alone is not enough. It fails loudly on a bad year, which is
    correct, but a reviewer judging candidates one at a time cannot possibly
    track word usage across 365 puzzles -- so "fix it by hand" is not a real
    instruction. Measured on the first real run: the top 120 candidates by
    quality contained 84 words over a cap of 3, because the generator samples
    endpoint pairs independently and popular mid-degree words like `desk` and
    `cake` recur constantly.

    So selection enforces the rules while choosing, exactly as the bank
    builder enforces uniqueness while choosing (planning.md 7.6). `check`
    then stays as independent verification of the finished archive -- belt
    and braces on the property that matters.

    Input must already be ordered by preference; the best candidate that
    still fits is always taken.

    `already_shipped` seeds the counters from an existing archive. The whole
    point of building a year one month at a time is that month two must not
    quietly reuse month one's words -- so the cap spans the archive, not the
    batch.
    """
    usage: Counter[str] = word_usage(already_shipped)
    seen_pairs: set[frozenset[str]] = {
        frozenset({p.start, p.end}) for p in already_shipped
    }
    seen_chains: set[tuple[str, ...]] = {p.solution for p in already_shipped}
    chosen: list[Candidate] = []
    skipped = {"word": 0, "pair": 0, "chain": 0}

    for candidate in candidates:
        if len(chosen) >= target:
            break

        pair = frozenset({candidate.path.start, candidate.path.end})
        if pair in seen_pairs:
            skipped["pair"] += 1
            continue
        if candidate.path.steps in seen_chains:
            skipped["chain"] += 1
            continue

        words = {*candidate.bank, candidate.path.start, candidate.path.end}
        if any(usage[w] >= max_word_reuse for w in words):
            skipped["word"] += 1
            continue

        chosen.append(candidate)
        seen_pairs.add(pair)
        seen_chains.add(candidate.path.steps)
        usage.update(words)

    return chosen, SelectionReport(
        considered=len(candidates),
        selected=len(chosen),
        skipped_word_cap=skipped["word"],
        skipped_duplicate_pair=skipped["pair"],
        skipped_duplicate_chain=skipped["chain"],
    )


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
