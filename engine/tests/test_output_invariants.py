"""THE golden test (planning.md 11).

Loads every shipped puzzle plus the verification subgraph, re-runs the
solver, and asserts exactly one solution. If this passes, the game is sound.

Runs on committed fixtures only -- no ConceptNet dump, no pickle, no network
(planning.md 7.10). That is a hard requirement: CI has none of those, and a
uniqueness guarantee nobody can check on a pull request is not a guarantee.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from linkage_engine.config import DEFAULT
from linkage_engine.data.codec import decode
from linkage_engine.data.exporters import read_verification_subgraph
from linkage_engine.domain.validator import count_solutions

pytestmark = pytest.mark.skipif(
    not DEFAULT.subgraph_path.exists() or not DEFAULT.puzzles_dir.exists(),
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


def test_id_and_date_stay_in_lockstep(puzzles, manifest):
    """A drift here shows the wrong puzzle number in every share."""
    epoch = date.fromisoformat(manifest["epoch"])
    first = manifest["firstId"]
    for puzzle in puzzles:
        expected = (epoch + timedelta(days=puzzle["id"] - first)).isoformat()
        assert puzzle["date"] == expected, puzzle["id"]


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
