"""Corpus-level rules applied to the shipped archive (planning.md 7.7.1).

`test_corpus.py` proves the rules work on synthetic input. This proves the
archive we actually ship obeys them -- individually-valid puzzles that make a
bad *year* are exactly what nothing else would catch.

Fixtures only. No dump, no pickle, no network.
"""

from __future__ import annotations

import json

import pytest

from linkage_engine.config import DEFAULT
from linkage_engine.data.codec import decode
from linkage_engine.domain.corpus import check, word_usage
from linkage_engine.domain.models import Puzzle

pytestmark = pytest.mark.skipif(
    not DEFAULT.puzzles_dir.exists() or not any(DEFAULT.puzzles_dir.glob("2*.json")),
    reason="no exported archive yet -- run `linkage export`",
)


@pytest.fixture(scope="module")
def puzzles() -> list[Puzzle]:
    out = []
    for path in sorted(DEFAULT.puzzles_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        row = decode(json.loads(path.read_text(encoding="utf-8"))["d"], path.stem)
        out.append(
            Puzzle(
                id=row["id"],
                date=row["date"],
                start=row["start"],
                end=row["end"],
                solution=tuple(row["solution"]),
                bank=tuple(row["bank"]),
            )
        )
    return out


def test_the_shipped_archive_passes_corpus_qc(puzzles):
    """The same check `export` runs, re-run against what landed on disk."""
    report = check(puzzles, DEFAULT.max_word_reuse, DEFAULT.word_reuse_window)
    assert report.puzzles == len(puzzles)


def test_no_word_exceeds_the_reuse_cap(puzzles):
    """Without this, `gravity` shows up in forty puzzles and the game feels
    small."""
    overused = {w: n for w, n in word_usage(puzzles).items() if n > DEFAULT.max_word_reuse}
    assert not overused, f"over-reused: {sorted(overused.items())[:10]}"


def test_no_duplicate_endpoint_pairs(puzzles):
    pairs = [frozenset({p.start, p.end}) for p in puzzles]
    assert len(set(pairs)) == len(pairs)


def test_no_repeated_solution_chains(puzzles):
    chains = [p.solution for p in puzzles]
    assert len(set(chains)) == len(chains)


def test_endpoints_are_varied(puzzles):
    """A start word reused across many puzzles reads as a rut even when every
    pairing is technically distinct."""
    from collections import Counter

    starts = Counter(p.start for p in puzzles)
    worst, count = starts.most_common(1)[0]
    assert count <= DEFAULT.max_word_reuse, f"{worst} starts {count} puzzles"
