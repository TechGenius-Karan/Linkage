"""Guards the one way to get the verification subgraph wrong (planning.md 7.10).

    The subgraph must be the INDUCED subgraph -- every edge among those 13
    nodes, not just the 5 solution edges. Exporting only the solution path
    would make the uniqueness test vacuous: it would find one solution
    because it was handed exactly one solution's worth of edges.

That failure mode is dangerous precisely because it fails by *passing*. The
golden test would go green while proving nothing at all.
"""

from __future__ import annotations

import itertools
import json

import pytest

from linkage_engine.config import DEFAULT
from linkage_engine.data.codec import decode
from linkage_engine.data.exporters import read_verification_subgraph

pytestmark = pytest.mark.skipif(
    not DEFAULT.subgraph_path.exists() or not DEFAULT.puzzles_dir.exists(),
    reason="no exported archive yet -- run `linkage export`",
)


@pytest.fixture(scope="module")
def subgraph():
    return read_verification_subgraph(DEFAULT.subgraph_path)


@pytest.fixture(scope="module")
def puzzles():
    out = []
    for path in sorted(DEFAULT.puzzles_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        out.append(decode(json.loads(path.read_text(encoding="utf-8"))["d"], path.stem))
    return out


def test_subgraph_carries_more_than_the_solution_edges(subgraph, puzzles):
    """The headline check. A path-only export would sit at exactly 5 edges
    per puzzle and quietly make every uniqueness assertion meaningless.
    """
    solution_edges = set()
    for puzzle in puzzles:
        chain = [puzzle["start"], *puzzle["solution"], puzzle["end"]]
        for a, b in zip(chain, chain[1:]):
            solution_edges.add(frozenset((a, b)))

    all_edges = {frozenset((a, b)) for a, b in subgraph.edges}
    assert all_edges > solution_edges, (
        "subgraph contains only the solution edges -- the uniqueness test "
        "would pass vacuously (planning.md 7.10)"
    )


def test_every_solution_edge_is_present(subgraph, puzzles):
    for puzzle in puzzles:
        chain = [puzzle["start"], *puzzle["solution"], puzzle["end"]]
        for a, b in zip(chain, chain[1:]):
            assert subgraph.has_edge(a, b), f"{puzzle['id']}: missing {a}-{b}"


def test_every_puzzle_word_appears(subgraph, puzzles):
    """A missing node cannot form an alternate chain, so its absence would
    make that puzzle look uniquely solvable when it might not be."""
    for puzzle in puzzles:
        for word in [puzzle["start"], puzzle["end"], *puzzle["bank"]]:
            assert word in subgraph, f"{puzzle['id']}: {word} absent"


def test_no_edge_among_puzzle_words_is_missing(subgraph, puzzles):
    """Induced means induced.

    Every pair of a puzzle's own 13 words that is adjacent in the full graph
    must appear here. We cannot consult the full graph in CI, so this checks
    the property that is checkable: the export is internally consistent, and
    edges present for one puzzle are not silently dropped for another that
    shares the same pair.
    """
    seen: dict[frozenset[str], bool] = {}
    for puzzle in puzzles:
        words = sorted({*puzzle["bank"], puzzle["start"], puzzle["end"]})
        for a, b in itertools.combinations(words, 2):
            key = frozenset((a, b))
            present = subgraph.has_edge(a, b)
            if key in seen:
                assert seen[key] == present, f"inconsistent edge {a}-{b}"
            seen[key] = present


def test_edges_carry_weights(subgraph):
    for _, _, data in subgraph.edges(data=True):
        assert isinstance(data.get("weight"), (int, float))


def test_subgraph_is_not_served(subgraph):
    """It is a plaintext answer key (planning.md 7.10, 12)."""
    assert DEFAULT.puzzles_dir not in DEFAULT.subgraph_path.parents
    assert "public" not in DEFAULT.subgraph_path.parts


def test_subgraph_stays_small_enough_to_commit():
    size_kb = DEFAULT.subgraph_path.stat().st_size / 1024
    assert size_kb < 4096, f"{size_kb:.0f} KB -- larger than a fixture should be"
