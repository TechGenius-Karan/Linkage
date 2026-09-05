"""Archive assembly (planning.md 3.1-3.3, 7.10)."""

from __future__ import annotations

import json

import networkx as nx
import pytest

from linkage_engine.config import Config
from linkage_engine.data import exporters
from linkage_engine.data.codec import decode
from linkage_engine.domain.models import Candidate, Path


def make_candidate(start="apple", end="ocean", steps=("newton", "gravity", "moon", "tide"),
                   extra=("pie", "salt", "orbit"), quality=0.8) -> Candidate:
    path = Path(
        start=start,
        end=end,
        steps=tuple(steps),
        weights=(2.4, 3.1, 2.8, 2.2, 2.9),
        relations=(("RelatedTo",),) * 5,
    )
    return Candidate(path=path, bank=tuple([*steps, *extra]), quality=quality)


@pytest.fixture
def cfg(tmp_path):
    return Config(repo_root=tmp_path)


# --------------------------------------------------------------------------
# Dates and identity
# --------------------------------------------------------------------------


def test_assign_dates_walks_forward_one_day_at_a_time():
    puzzles = exporters.assign_dates([make_candidate() for _ in range(3)], "2026-10-01")
    assert [p.id for p in puzzles] == [1, 2, 3]
    assert [p.date for p in puzzles] == ["2026-10-01", "2026-10-02", "2026-10-03"]


def test_id_and_date_stay_in_lockstep_across_a_month_boundary():
    """A drift here shows the wrong puzzle number in every share."""
    puzzles = exporters.assign_dates([make_candidate() for _ in range(40)], "2026-10-01")
    from datetime import date, timedelta

    epoch = date.fromisoformat("2026-10-01")
    for puzzle in puzzles:
        assert puzzle.date == (epoch + timedelta(days=puzzle.id - 1)).isoformat()


def test_content_hash_is_stable_and_survives_a_reshuffled_bank():
    """Review decisions are keyed by this, so a new shuffle must not orphan a
    judgement a person already made (planning.md 7.7)."""
    a = make_candidate()
    b = Candidate(path=a.path, bank=tuple(reversed(a.bank)), quality=0.1)
    assert a.content_hash() == b.content_hash()


def test_content_hash_changes_with_the_solution():
    a = make_candidate()
    b = make_candidate(steps=("newton", "gravity", "tide", "moon"))
    assert a.content_hash() != b.content_hash()


# --------------------------------------------------------------------------
# Shipped files
# --------------------------------------------------------------------------


def test_per_day_files_decode_back_to_the_puzzle(cfg):
    puzzles = exporters.assign_dates([make_candidate()], "2026-10-01")
    paths = exporters.write_puzzles(cfg, puzzles)

    payload = json.loads(paths[0].read_text(encoding="utf-8"))
    assert set(payload) == {"v", "d"}
    decoded = decode(payload["d"], puzzles[0].date)
    assert decoded["solution"] == list(puzzles[0].solution)
    assert decoded["id"] == 1


def test_shipped_payload_carries_no_meta(cfg):
    """`meta` is dead payload weight and a mild hint (planning.md 3.1)."""
    puzzles = exporters.assign_dates([make_candidate()], "2026-10-01")
    paths = exporters.write_puzzles(cfg, puzzles)
    decoded = decode(json.loads(paths[0].read_text())["d"], puzzles[0].date)
    assert "meta" not in decoded
    assert set(decoded) == {
        "schemaVersion", "id", "date", "start", "end", "solution", "bank",
    }


def test_answers_are_not_readable_in_the_shipped_file(cfg):
    puzzles = exporters.assign_dates([make_candidate()], "2026-10-01")
    raw = exporters.write_puzzles(cfg, puzzles)[0].read_text(encoding="utf-8")
    for word in puzzles[0].solution:
        assert word not in raw


def test_manifest_describes_the_archive(cfg):
    puzzles = exporters.assign_dates([make_candidate() for _ in range(5)], "2026-10-01")
    manifest = json.loads(exporters.write_manifest(cfg, puzzles).read_text())
    assert manifest == {
        "schemaVersion": cfg.schema_version,
        "epoch": "2026-10-01",
        "count": 5,
        "firstId": 1,
    }


def test_licence_notice_names_conceptnet_and_the_share_alike_terms(cfg):
    """CC BY-SA 4.0 is a legal requirement, not a courtesy (planning.md 12.2)."""
    text = exporters.write_licence_notice(cfg).read_text(encoding="utf-8")
    assert "ConceptNet" in text
    assert "CC BY-SA 4.0" in text or "by-sa/4.0" in text


# --------------------------------------------------------------------------
# Verification subgraph (planning.md 7.10)
# --------------------------------------------------------------------------


def _graph_with_extra_edges() -> nx.Graph:
    g = nx.Graph()
    chain = ("apple", "newton", "gravity", "moon", "tide", "ocean")
    for a, b in zip(chain, chain[1:]):
        g.add_edge(a, b, weight=3.0)
    # Edges among bank words that are NOT on the solution path. These are the
    # ones an alternate chain would use, so they must survive export.
    g.add_edge("pie", "salt", weight=1.5)
    g.add_edge("orbit", "moon", weight=2.0)
    g.add_edge("faraway", "unrelated", weight=9.0)  # must NOT be exported
    return g


def test_subgraph_is_induced_not_just_the_solution_path(cfg):
    """The single way to get this file wrong, and it fails by *passing*.

    Exporting only the five solution edges would make the uniqueness test
    vacuous -- it would find one solution because it was handed exactly one
    solution's worth of edges.
    """
    graph = _graph_with_extra_edges()
    puzzles = exporters.assign_dates([make_candidate()], "2026-10-01")
    edges = exporters.build_verification_subgraph(graph, puzzles)
    pairs = {frozenset((a, b)) for a, b, _ in edges}

    assert frozenset(("orbit", "moon")) in pairs  # off-path, must be kept
    assert frozenset(("pie", "salt")) in pairs
    assert len(pairs) > 5


def test_subgraph_excludes_words_no_puzzle_uses(cfg):
    graph = _graph_with_extra_edges()
    puzzles = exporters.assign_dates([make_candidate()], "2026-10-01")
    words = {w for a, b, _ in exporters.build_verification_subgraph(graph, puzzles)
             for w in (a, b)}
    assert "faraway" not in words


def test_subgraph_roundtrips_into_a_usable_graph(cfg):
    graph = _graph_with_extra_edges()
    puzzles = exporters.assign_dates([make_candidate()], "2026-10-01")
    path = exporters.write_verification_subgraph(cfg, graph, puzzles)

    rebuilt = exporters.read_verification_subgraph(path)
    assert rebuilt.has_edge("apple", "newton")
    assert rebuilt["apple"]["newton"]["weight"] == pytest.approx(3.0)


def test_subgraph_lands_outside_the_web_root(cfg):
    """It is a plaintext answer key. Serving it would undo planning.md 3.2."""
    graph = _graph_with_extra_edges()
    puzzles = exporters.assign_dates([make_candidate()], "2026-10-01")
    path = exporters.write_verification_subgraph(cfg, graph, puzzles)
    assert cfg.puzzles_dir not in path.parents
    assert path.parent.name == "fixtures"


# --------------------------------------------------------------------------
# Candidates and decisions
# --------------------------------------------------------------------------


def test_candidates_are_written_best_first(cfg):
    candidates = [
        make_candidate(start="a", quality=0.3),
        make_candidate(start="b", quality=0.9),
        make_candidate(start="c", quality=0.6),
    ]
    exporters.write_candidates(cfg.candidates_path, candidates)
    rows = exporters.read_candidates(cfg.candidates_path)
    assert [r["quality"] for r in rows] == [0.9, 0.6, 0.3]


def test_reading_missing_candidates_gives_an_actionable_error(cfg):
    with pytest.raises(FileNotFoundError, match="linkage generate"):
        exporters.read_candidates(cfg.candidates_path)


def test_decisions_roundtrip_and_default_to_empty(cfg):
    assert exporters.read_decisions(cfg.decisions_path) == {}
    exporters.write_decisions(cfg.decisions_path, {"abc": "accept"})
    assert exporters.read_decisions(cfg.decisions_path) == {"abc": "accept"}
