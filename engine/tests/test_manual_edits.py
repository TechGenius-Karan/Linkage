"""Hand-edited puzzles, end to end (docs/admin.md 11).

The rule under test is the one the plan settles: **the reviewer decides whether
a puzzle holds.** ConceptNet is overruled, and the machine keeps exactly one
veto -- uniqueness, and the chords that manufacture it.

The load-bearing test here is the last one. A reviewer can assert a link
ConceptNet does not carry, and the golden test re-solves every shipped puzzle
from `verification-subgraph.json` alone on a machine that has never seen the
1.2 GB dump. If an asserted link did not reach that file, the puzzle would
re-solve to *zero* answers and CI would reject it -- not for being bad, but for
being unprovable. So the assertion has to travel the whole way.
"""

from __future__ import annotations

import json

import networkx as nx
import pytest
from typer.testing import CliRunner

from linkage_engine.cli import app
from linkage_engine.config import Config
from linkage_engine.data import exporters, graph_store
from linkage_engine.data.stemming import IdentityStemmer
from linkage_engine.domain import decisions as dec
from linkage_engine.domain import refine
from linkage_engine.domain.validator import solve_all

runner = CliRunner()
TODAY = "2026-09-11"

CHAIN = ("whale", "ocean", "azure", "skies", "birds", "wings")
DECOYS = ("cloud", "shark", "nest", "coral", "reef", "storm")


@pytest.fixture
def graph():
    g = nx.Graph()
    for a, b in zip(CHAIN, CHAIN[1:]):
        g.add_edge(a, b, weight=3.0, relations=("RelatedTo",))
    # Every decoy hangs off one solution word and goes nowhere.
    for anchor, decoy in zip(("ocean", "skies", "birds", "ocean", "skies", "azure"), DECOYS):
        g.add_edge(anchor, decoy, weight=2.0, relations=("RelatedTo",))
    return g


@pytest.fixture
def cfg(tmp_path):
    return Config(repo_root=tmp_path, chain_length=4, bank_size_min=6)


def puzzle(start="whale", end="wings", solution=CHAIN[1:-1]) -> dec.Puzzle:
    return dec.Puzzle(
        start=start,
        end=end,
        solution=tuple(solution),
        bank=tuple(sorted({*solution, *DECOYS})),
    )


def check(cfg, graph, p, edges=()):
    return refine.validate_puzzle(cfg, graph, IdentityStemmer(), p, edges)


# --------------------------------------------------------------------------
# The reviewer's judgement governs
# --------------------------------------------------------------------------


class TestConceptNetIsOverruled:
    def test_a_rung_conceptnet_lacks_is_reported_not_refused_once_asserted(self, cfg, graph):
        edited = puzzle(start="shingle")
        assert not check(cfg, graph, edited).ok

        verdict = check(cfg, graph, edited, (("shingle", "ocean", 2.0),))
        assert verdict.ok
        assert verdict.refusals == ()

    def test_and_the_reviewer_is_told_they_are_the_source(self, cfg, graph):
        # Not a block. They should know which rung rests on their word while
        # they are deciding (docs/admin.md 11.2).
        verdict = check(cfg, graph, puzzle(start="shingle"), (("shingle", "ocean", 2.0),))
        assert verdict.asserted_links == (0,)
        assert any("rests on your word" in n for n in verdict.notes)

    def test_an_unasserted_broken_rung_names_the_rung(self, cfg, graph):
        # "Invalid" is unactionable; naming the pair is a next step.
        verdict = check(cfg, graph, puzzle(start="shingle"))
        assert any("shingle -> ocean" in r for r in verdict.refusals)

    def test_an_endpoint_can_be_rewritten_entirely(self, cfg, graph):
        verdict = check(
            cfg, graph, puzzle(start="rooftop", end="feathers"),
            (("rooftop", "ocean", 2.0), ("birds", "feathers", 2.0)),
        )
        assert verdict.ok
        assert verdict.asserted_links == (0, 4)

    def test_an_answer_word_can_be_rewritten(self, cfg, graph):
        edited = dec.apply_puzzle_edits(
            "whale", "wings", CHAIN[1:-1], sorted({*CHAIN[1:-1], *DECOYS}),
            (dec.WordEdit(field="solution", index=1, removed="azure", added="cobalt"),),
        )
        verdict = check(cfg, graph, edited, (("ocean", "cobalt", 2.0), ("cobalt", "skies", 2.0)))
        assert verdict.ok, verdict.refusals

    def test_the_old_answer_word_does_not_linger_in_the_bank(self, cfg, graph):
        # It would sit there as a decoy that used to be the answer. Nothing
        # else would catch it: uniqueness passes, because a stale answer word
        # is just a decoy that happens not to fit.
        edited = dec.apply_puzzle_edits(
            "whale", "wings", CHAIN[1:-1], sorted({*CHAIN[1:-1], *DECOYS}),
            (dec.WordEdit(field="solution", index=1, removed="azure", added="cobalt"),),
        )
        assert "azure" not in edited.bank
        assert "cobalt" in edited.bank


# --------------------------------------------------------------------------
# The one veto the reviewer does not get
# --------------------------------------------------------------------------


class TestUniquenessSurvivesEverything:
    def test_an_asserted_link_that_creates_a_second_answer_is_refused(self, cfg, graph):
        verdict = check(cfg, graph, puzzle(), (("whale", "cloud", 3.0), ("cloud", "azure", 3.0)))
        assert not verdict.ok
        assert any("second arrangement" in r for r in verdict.refusals)

    def test_the_refusal_names_the_other_answer(self, cfg, graph):
        verdict = check(cfg, graph, puzzle(), (("whale", "cloud", 3.0), ("cloud", "azure", 3.0)))
        assert any("cloud" in r for r in verdict.refusals)

    def test_an_asserted_chord_is_refused(self, cfg, graph):
        # A chord hands the player a shortcut past a rung, which is how a
        # second ordering gets manufactured in the first place.
        verdict = check(cfg, graph, puzzle(), (("whale", "skies", 3.0),))
        assert any("shortcut" in r for r in verdict.refusals)

    def test_a_bank_with_no_answer_at_all_is_refused(self, cfg, graph):
        verdict = check(cfg, graph, puzzle(start="shingle"), (("shingle", "cloud", 2.0),))
        assert not verdict.ok

    def test_asserting_a_link_never_mutates_the_shared_graph(self, cfg, graph):
        # The server holds one graph for its whole life. An edit previewed and
        # then abandoned must not leave a link behind for the next puzzle.
        before = graph.number_of_edges()
        check(cfg, graph, puzzle(), (("whale", "cloud", 3.0),))
        assert graph.number_of_edges() == before
        assert not graph.has_edge("whale", "cloud")


class TestShapeIsStillEnforced:
    """Not judgement -- these are facts about the file format."""

    def test_a_word_that_cannot_be_normalised(self, cfg, graph):
        verdict = check(cfg, graph, puzzle(start="Whale Shark"))
        assert any("lowercase" in r for r in verdict.refusals)

    def test_a_word_that_is_too_long_to_fit_a_tile(self, cfg, graph):
        verdict = check(cfg, graph, puzzle(start="extraordinarily"))
        assert any("letters" in r for r in verdict.refusals)

    def test_an_endpoint_sitting_in_its_own_bank(self, cfg, graph):
        p = puzzle()
        verdict = check(cfg, graph, dec.Puzzle(p.start, p.end, p.solution, (*p.bank, "whale")))
        assert any("endpoint" in r for r in verdict.refusals)


# --------------------------------------------------------------------------
# The whole way through: edit -> approve -> export -> CI re-solve
# --------------------------------------------------------------------------


def test_an_asserted_link_reaches_the_fixture_ci_re_solves_from(tmp_path, monkeypatch, graph):
    """The load-bearing one (docs/admin.md 11.2).

    CI has no ConceptNet dump. If a hand-asserted rung is not in
    `verification-subgraph.json`, the shipped puzzle re-solves to zero answers
    and the golden test rejects it for being unprovable rather than wrong.
    """
    cfg = Config(
        repo_root=tmp_path, chain_length=4, bank_size_min=6, batch_size=1, launch_week_size=1
    )
    cfg.engine_dir.mkdir(parents=True, exist_ok=True)
    cfg.candidates_path.write_text(
        json.dumps([{
            "hash": "aaa",
            "start": "whale",
            "end": "wings",
            "solution": list(CHAIN[1:-1]),
            "bank": sorted({*CHAIN[1:-1], *DECOYS}),
            "quality": 0.9,
            "weights": [3.0] * 5,
            "relations": [["RelatedTo"]] * 5,
        }]),
        encoding="utf-8",
    )
    graph_store.save(
        graph,
        cfg.graph_path,
        graph_store.build_meta(cfg, conceptnet_sha256="test", vocab_size=len(graph)),
    )
    # The reviewer swaps the start word for one ConceptNet has never linked,
    # and asserts the link themselves.
    exporters.write_decisions(cfg.decisions_path, {
        "aaa": dec.approve(
            TODAY,
            edits=(dec.WordEdit(field="start", removed="whale", added="shingle"),),
            manual_edges=(("shingle", "ocean", 2.0),),
        )
    })
    monkeypatch.setattr("linkage_engine.cli.DEFAULT", cfg)

    result = runner.invoke(app, ["export"])
    assert result.exit_code == 0, result.output
    assert "asserted by the reviewer" in result.output

    shipped = exporters.read_archive(cfg)[0]
    assert shipped.start == "shingle"

    # Now do exactly what CI does: rebuild the graph from the committed fixture
    # -- nothing else -- and re-solve.
    fixture = exporters.read_verification_subgraph(cfg.subgraph_path)
    assert fixture.has_edge("shingle", "ocean"), "the asserted link never shipped"
    found = solve_all(fixture, shipped.start, shipped.end, shipped.bank, cfg.chain_length)
    assert found == [tuple(shipped.solution)], found


def test_hints_are_ranked_on_the_edited_chain_not_the_generated_one(cfg, graph):
    """Stale weights would offer the wrong hint words.

    `hints.obviousness()` ranks answer words by the strength of the links
    either side of them, so a chain whose rungs have moved needs its weights
    rebuilt or the puzzle ships hints for a chain it no longer has.
    """
    edited = puzzle(start="shingle")
    path = refine.effective_path(graph, edited, (("shingle", "ocean", 7.5),))
    assert path.start == "shingle"
    assert path.weights[0] == 7.5
    assert path.relations[0] == (refine.ASSERTED_RELATION,)
