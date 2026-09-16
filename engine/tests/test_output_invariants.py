"""THE golden test (planning.md 11).

Loads every shipped puzzle plus the verification subgraph, re-runs the
solver, and asserts exactly one solution. If this passes, the game is sound.

Runs on committed fixtures only -- no ConceptNet dump, no pickle, no network
(planning.md 7.10). That is a hard requirement: CI has none of those, and a
uniqueness guarantee nobody can check on a pull request is not a guarantee.
"""

from __future__ import annotations

import json

import pytest

from linkage_engine.config import DEFAULT
from linkage_engine.data.codec import decode
from linkage_engine.data.exporters import read_verification_subgraph
from linkage_engine.domain.validator import count_solutions

def _has_shipped_puzzles() -> bool:
    """`puzzles_dir` holding only `manifest.json`/`README.md` is an empty
    archive, not a missing one -- skip either way rather than failing on
    "archive is present but empty"."""
    return any(p.name != "manifest.json" for p in DEFAULT.puzzles_dir.glob("*.json"))


pytestmark = pytest.mark.skipif(
    not DEFAULT.subgraph_path.exists() or not _has_shipped_puzzles(),
    reason="no exported archive yet -- run `linkage export`",
)


@pytest.fixture(scope="module")
def subgraph():
    return read_verification_subgraph(DEFAULT.subgraph_path)


@pytest.fixture(scope="module")
def puzzles():
    """Every shipped puzzle, decoded from its own per-day file."""
    out = []
    for path in sorted(DEFAULT.puzzles_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        out.append(decode(payload["d"], path.stem))
    assert out, "archive is present but empty"
    return out


@pytest.fixture(scope="module")
def manifest():
    return json.loads((DEFAULT.puzzles_dir / "manifest.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# The property the whole game rests on
# --------------------------------------------------------------------------


def test_every_puzzle_has_exactly_one_solution(subgraph, puzzles):
    """A second valid arrangement means a player can be right and be told
    they are wrong. That is a broken promise, not a difficulty setting."""
    ambiguous = []
    for puzzle in puzzles:
        n = count_solutions(
            subgraph, puzzle["start"], puzzle["end"], puzzle["bank"], len(puzzle["solution"])
        )
        if n != 1:
            ambiguous.append((puzzle["id"], puzzle["date"], n))
    assert not ambiguous, f"puzzles with != 1 solution: {ambiguous[:10]}"


def test_the_stated_solution_is_the_solution(subgraph, puzzles):
    from linkage_engine.domain.validator import chain_is_valid

    for puzzle in puzzles:
        assert chain_is_valid(
            subgraph, puzzle["start"], puzzle["end"], puzzle["solution"]
        ), f"puzzle {puzzle['id']} does not solve with its own answer"


# --------------------------------------------------------------------------
# Per-puzzle structure
# --------------------------------------------------------------------------


def test_no_direct_start_to_end_edge(subgraph, puzzles):
    for puzzle in puzzles:
        assert not subgraph.has_edge(puzzle["start"], puzzle["end"]), puzzle["id"]


def test_solution_length_matches_the_chain_length(puzzles):
    for puzzle in puzzles:
        assert len(puzzle["solution"]) == DEFAULT.chain_length, puzzle["id"]


def test_bank_size_is_within_spec(puzzles):
    for puzzle in puzzles:
        assert DEFAULT.bank_size_min <= len(puzzle["bank"]) <= 12, puzzle["id"]


def test_bank_contains_the_solution(puzzles):
    for puzzle in puzzles:
        assert set(puzzle["solution"]).issubset(puzzle["bank"]), puzzle["id"]


def test_bank_has_no_duplicates(puzzles):
    """Two identical tiles would be indistinguishable and break tileId-as-word."""
    for puzzle in puzzles:
        assert len(set(puzzle["bank"])) == len(puzzle["bank"]), puzzle["id"]


def test_endpoints_are_not_in_the_bank(puzzles):
    for puzzle in puzzles:
        assert puzzle["start"] not in puzzle["bank"], puzzle["id"]
        assert puzzle["end"] not in puzzle["bank"], puzzle["id"]


def test_every_word_is_normalised(puzzles):
    """planning.md 3.1.1: lowercase ASCII, no multiword, sized for a tile."""
    from linkage_engine.domain.filters import is_normalised

    for puzzle in puzzles:
        for word in [puzzle["start"], puzzle["end"], *puzzle["bank"]]:
            assert is_normalised(word), f"{puzzle['id']}: {word!r}"
            assert DEFAULT.word_min_len <= len(word) <= DEFAULT.word_max_len


def test_no_two_bank_words_share_a_stem(puzzles):
    """`moon` beside `moons` reads as sloppiness (planning.md 7.6)."""
    from linkage_engine.data.stemming import PorterStemmerAdapter

    stemmer = PorterStemmerAdapter()
    for puzzle in puzzles:
        stems = [stemmer.stem(w) for w in puzzle["bank"]]
        assert len(set(stems)) == len(stems), f"{puzzle['id']}: {puzzle['bank']}"


# --------------------------------------------------------------------------
# Identity and the manifest
# --------------------------------------------------------------------------


def test_dates_strictly_increase_with_id(puzzles):
    """Ids are assignment order and stay contiguous (the next test); dates
    may skip a day the reviewer left empty, but must never repeat or run
    backwards -- that would show a puzzle number moving the wrong way in a
    share (planning.md 3.3)."""
    ordered = sorted(puzzles, key=lambda p: p["id"])
    for prev, curr in zip(ordered, ordered[1:]):
        assert curr["id"] == prev["id"] + 1, (prev["id"], curr["id"])
        assert curr["date"] > prev["date"], (curr["id"], prev["date"], curr["date"])


def test_ids_are_contiguous(puzzles, manifest):
    ids = sorted(p["id"] for p in puzzles)
    assert ids == list(range(manifest["firstId"], manifest["firstId"] + len(ids)))


def test_manifest_count_matches_the_files_on_disk(puzzles, manifest):
    assert manifest["count"] == len(puzzles)


def test_schema_version_is_consistent(puzzles, manifest):
    for puzzle in puzzles:
        assert puzzle["schemaVersion"] == manifest["schemaVersion"]


def test_filename_matches_the_puzzle_date(puzzles):
    """The date is the decryption key, so a mismatch is unrecoverable."""
    for path in sorted(DEFAULT.puzzles_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert decode(payload["d"], path.stem)["date"] == path.stem
