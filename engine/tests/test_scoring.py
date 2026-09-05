"""Quality ranking (planning.md 7.6, 7.7).

Phase 1 closed the yield risk, which moved the project's whole risk onto
Risk #1 -- "valid but not fun". Finding paths is free; choosing them is
everything, and this is what orders the review queue.

These tests pin *relative* behaviour, never absolute scores. Absolute values
are taste and will be retuned; the orderings are the contract.
"""

from __future__ import annotations

import networkx as nx
import pytest

from linkage_engine.domain.models import Path
from linkage_engine.domain.scoring import COMPONENT_WEIGHTS, QualityScorer

SCORER = QualityScorer()


def path(weights=(3.0, 3.0, 3.0, 3.0, 3.0), relations=None) -> Path:
    relations = relations or (("RelatedTo",),) * 5
    return Path("s", "e", ("w1", "w2", "w3", "w4"), tuple(weights), tuple(relations))


def graph_for(path_obj: Path, shared_neighbours: int = 0) -> nx.Graph:
    g = nx.Graph()
    nodes = path_obj.nodes
    for (a, b), w in zip(zip(nodes, nodes[1:]), path_obj.weights):
        g.add_edge(a, b, weight=w)
    for i in range(shared_neighbours):
        g.add_edge(path_obj.start, f"shared{i}", weight=1.0)
        g.add_edge(path_obj.end, f"shared{i}", weight=1.0)
    return g


def score(path_obj: Path, shared: int = 0) -> float:
    return SCORER.score(graph_for(path_obj, shared), path_obj)[0]


# --------------------------------------------------------------------------
# Shape
# --------------------------------------------------------------------------


def test_component_weights_sum_to_one_so_quality_reads_as_a_fraction():
    assert sum(COMPONENT_WEIGHTS.values()) == pytest.approx(1.0)


def test_score_is_bounded():
    for weights in [(0.1,) * 5, (99.0,) * 5, (0.1, 99.0, 0.1, 99.0, 0.1)]:
        assert 0.0 <= score(path(weights)) <= 1.0


def test_breakdown_names_every_component():
    _, breakdown = SCORER.score(graph_for(path()), path())
    assert dict(breakdown).keys() == COMPONENT_WEIGHTS.keys()


def test_breakdown_is_sorted_for_stable_output():
    _, breakdown = SCORER.score(graph_for(path()), path())
    assert [k for k, _ in breakdown] == sorted(COMPONENT_WEIGHTS)


# --------------------------------------------------------------------------
# Orderings -- the actual contract
# --------------------------------------------------------------------------


def test_a_strong_chain_outranks_a_weak_one():
    assert score(path((4.0,) * 5)) > score(path((2.0,) * 5))


def test_one_weak_rung_drags_the_whole_chain_down():
    """The weakest link is what makes a puzzle feel unfair, so it must
    outweigh four strong rungs (planning.md 7.4)."""
    assert score(path((4.0, 4.0, 0.5, 4.0, 4.0))) < score(path((3.0,) * 5))


def test_unrelated_endpoints_beat_obviously_related_ones():
    """`apple -> ocean` is a puzzle; `apple -> fruit` is a definition."""
    p = path()
    assert score(p, shared=0) > score(p, shared=6)


def test_varied_relations_beat_five_identical_hops():
    monotone = path(relations=(("RelatedTo",),) * 5)
    varied = path(
        relations=(("IsA",), ("AtLocation",), ("UsedFor",), ("Causes",), ("PartOf",))
    )
    assert score(varied) > score(monotone)


def test_a_specific_chain_beats_one_routed_through_hubs():
    """The retune that came out of reading 900 real candidates.

    Edge strength alone ranked `ocean -> sailing -> fun -> dancing` above
    `statement -> answer -> reply -> echo`. Vague words earn strong edges by
    co-occurring with everything, so specificity has to counterweight them.
    """
    p = path()
    specific = graph_for(p)
    vague = graph_for(p)
    for step in p.steps:
        for i in range(150):
            vague.add_edge(step, f"{step}_n{i}", weight=1.0)

    assert SCORER.score(specific, p)[0] > SCORER.score(vague, p)[0]


def test_specificity_floors_at_zero_for_extreme_hubs():
    p = path()
    g = graph_for(p)
    for step in p.steps:
        for i in range(500):
            g.add_edge(step, f"{step}_n{i}", weight=1.0)
    assert dict(SCORER.score(g, p)[1])["specificity"] == 0.0


def test_an_even_chain_beats_a_lopsided_one():
    even = path((3.0, 3.0, 3.0, 3.0, 3.0))
    lopsided = path((0.5, 6.0, 0.5, 6.0, 0.5))
    assert score(even) > score(lopsided)


def test_scoring_is_deterministic():
    p = path()
    g = graph_for(p)
    assert SCORER.score(g, p) == SCORER.score(g, p)


def test_quality_is_rounded_for_stable_serialisation():
    quality, _ = SCORER.score(graph_for(path()), path())
    assert quality == round(quality, 4)
