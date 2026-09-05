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

from collections import Counter, deque
from dataclasses import dataclass
from typing import Iterable, Sequence

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


def visible_words(puzzle: Puzzle) -> set[str]:
    """Every word a player can see: the bank plus both endpoints."""
    return {*puzzle.bank, puzzle.start, puzzle.end}


class RollingUsage:
    """Word counts over a sliding window of recent puzzles.

    The window is what makes reuse a *seasonal* limit rather than a lifetime
    quota. A word blocked today falls out the back of the window later and
    becomes available again -- which matches how memory works and stops the
    archive slowly exhausting its own vocabulary.

    Holds `window - 1` entries, because the puzzle being tested occupies the
    last slot of its own window.
    """

    def __init__(self, window: int) -> None:
        if window < 1:
            raise ValueError(f"window must be >= 1, got {window}")
        self.window = window
        self._recent: deque[set[str]] = deque()
        self._counts: Counter[str] = Counter()

    def count(self, word: str) -> int:
        return self._counts[word]

    def would_exceed(self, words: Iterable[str], cap: int) -> bool:
        return any(self._counts[w] >= cap for w in words)

    def push(self, words: Iterable[str]) -> None:
        words = set(words)
        self._recent.append(words)
        self._counts.update(words)
        while len(self._recent) > self.window - 1:
            self._counts.subtract(self._recent.popleft())

    def seed(self, puzzles: Iterable[Puzzle]) -> None:
        for puzzle in puzzles:
            self.push(visible_words(puzzle))


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
    window: int,
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

    `already_shipped` seeds the window from an existing archive. The whole
    point of building a year one month at a time is that month two must not
    quietly reuse month one's words -- so the limit spans the archive, not
    the batch.

    Endpoint pairs and solution chains are barred **permanently**, not by
    window. Word reuse is about texture and fades from memory; shipping the
    literal same puzzle twice is a defect at any distance.

    This is a **single greedy pass**: a candidate skipped for the word cap is
    not reconsidered later in the same call, even though the window may have
    slid far enough to admit it. That cannot bite at real settings -- a batch
    of 30 cannot slide a 120-puzzle window past anything -- and skipped
    candidates stay in the pool for the next batch, where the window has
    genuinely moved. Adding backtracking would be machinery for a case the
    configuration forbids.
    """
    usage = RollingUsage(window)
    usage.seed(already_shipped)

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
        if usage.would_exceed(words, max_word_reuse):
            skipped["word"] += 1
            continue

        chosen.append(candidate)
        seen_pairs.add(pair)
        seen_chains.add(candidate.path.steps)
        usage.push(words)

    return chosen, SelectionReport(
        considered=len(candidates),
        selected=len(chosen),
        skipped_word_cap=skipped["word"],
        skipped_duplicate_pair=skipped["pair"],
        skipped_duplicate_chain=skipped["chain"],
    )


def check(puzzles: Sequence[Puzzle], max_word_reuse: int, window: int) -> CorpusReport:
    """Validate the whole archive. Raises `CorpusViolation` on any breach.

    Independent verification of what `select_diverse` enforced while
    choosing -- belt and braces on the properties that decide whether a year
    of puzzles feels varied.
    """
    problems: list[str] = []

    # -- word repetition, within a rolling window --------------------------
    # Must use the same windowed rule the selector applies, or the two
    # disagree and a valid archive fails its own check.
    ordered = sorted(puzzles, key=lambda p: p.id)
    rolling = RollingUsage(window)
    breaches: list[tuple[str, int, int]] = []  # word, puzzle id, count in window
    for puzzle in ordered:
        words = visible_words(puzzle)
        for word in sorted(words):
            seen = rolling.count(word)
            if seen >= max_word_reuse:
                breaches.append((word, puzzle.id, seen + 1))
        rolling.push(words)

    if breaches:
        shown = ", ".join(f"{w} x{n} by #{pid}" for w, pid, n in breaches[:10])
        problems.append(
            f"{len(breaches)} word(s) exceed MAX_WORD_REUSE={max_word_reuse} "
            f"within a {window}-puzzle window: {shown}"
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

    lifetime = word_usage(puzzles)
    return CorpusReport(
        puzzles=len(puzzles),
        distinct_words=len(lifetime),
        most_reused=tuple(lifetime.most_common(10)),
    )
