"""Graph assembly and pruning (planning.md 7.2, 7.3)."""

from __future__ import annotations

import networkx as nx
import pytest

from linkage_engine.data.conceptnet import ConceptNetLoader
from linkage_engine.domain import graph_builder
from linkage_engine.domain.models import Assertion
from linkage_engine.domain.relations import is_allowed

VOCAB = frozenset({"a", "b", "c", "d"})


def A(start, end, relation="RelatedTo", weight=2.0):
    return Assertion(start=start, end=end, relation=relation, weight=weight)


def test_builds_an_undirected_graph():
    g = graph_builder.build([A("a", "b")], VOCAB, 1.0)
    assert g.has_edge("a", "b")
    assert g.has_edge("b", "a")


def test_self_loops_are_dropped():
    g = graph_builder.build([A("a", "a")], VOCAB, 1.0)
    assert g.number_of_edges() == 0


def test_endpoints_outside_the_vocabulary_are_dropped():
    g = graph_builder.build([A("a", "zzz")], VOCAB, 1.0)
    assert g.number_of_edges() == 0


def test_weights_below_the_threshold_are_dropped():
    g = graph_builder.build([A("a", "b", weight=0.5)], VOCAB, 1.0)
    assert g.number_of_edges() == 0


def test_duplicate_pairs_keep_the_maximum_weight():
    """A pair asserted twice is better evidence, not worse."""
    g = graph_builder.build(
        [A("a", "b", weight=1.2), A("a", "b", weight=3.4), A("a", "b", weight=2.0)],
        VOCAB,
        1.0,
    )
    assert g.number_of_edges() == 1
    assert g["a"]["b"]["weight"] == pytest.approx(3.4)


def test_duplicate_pairs_union_their_relations_deterministically():
    g = graph_builder.build(
        [
            A("a", "b", relation="UsedFor"),
            A("a", "b", relation="RelatedTo"),
            A("b", "a", relation="IsA"),  # reversed order, same undirected pair
        ],
        VOCAB,
        1.0,
    )
    # Sorted tuple, not a set: the pickled artifact must be byte-stable.
    assert g["a"]["b"]["relations"] == ("IsA", "RelatedTo", "UsedFor")


def test_relations_are_recorded_for_the_reversed_direction_too():
    """The pair key is order-normalised, so b->a must not create a second edge."""
    g = graph_builder.build([A("a", "b"), A("b", "a", relation="IsA")], VOCAB, 1.0)
    assert g.number_of_edges() == 1
    assert set(g["a"]["b"]["relations"]) == {"RelatedTo", "IsA"}


def test_build_is_order_independent_for_weights():
    ascending = graph_builder.build(
        [A("a", "b", weight=1.5), A("a", "b", weight=3.0)], VOCAB, 1.0
    )
    descending = graph_builder.build(
        [A("a", "b", weight=3.0), A("a", "b", weight=1.5)], VOCAB, 1.0
    )
    assert ascending["a"]["b"]["weight"] == descending["a"]["b"]["weight"]


# --------------------------------------------------------------------------
# Pruning
# --------------------------------------------------------------------------


#: Big enough that the 99th percentile actually lands below the hub. With a
#: small star the hub *is* the 99th percentile -- nearest-rank on 53 values
#: puts P99 at the maximum, so nothing exceeds it and nothing is removed.
#: That is correct behaviour, and a reminder that percentile pruning needs a
#: population to be meaningful.
SPOKES = 200


def _star(spokes: int = SPOKES) -> nx.Graph:
    """A hub with `spokes` leaves, plus a separate low-degree pair."""
    g = nx.Graph()
    for i in range(spokes):
        g.add_edge("hub", f"leaf{i}", weight=1.0)
    g.add_edge("x", "y", weight=1.0)
    return g


def test_prune_hubs_removes_the_hub_and_reports_the_cutoff():
    g = _star()
    removed, cutoff = graph_builder.prune_hubs(g, 99.0)
    assert removed == {"hub"}
    assert "hub" not in g
    assert cutoff == 1


def test_percentile_pruning_is_a_no_op_on_a_tiny_population():
    """Documents the limitation above rather than pretending it away."""
    g = _star(spokes=50)
    removed, _ = graph_builder.prune_hubs(g, 99.0)
    assert removed == set()


def test_prune_hubs_uses_strictly_greater_than():
    """A flat degree distribution must not be gutted."""
    g = nx.cycle_graph(10)  # every node has degree exactly 2
    removed, cutoff = graph_builder.prune_hubs(g, 99.0)
    assert removed == set()
    assert cutoff == 2
    assert g.number_of_nodes() == 10


def test_drop_isolated_cleans_up_after_hub_removal():
    g = _star()
    graph_builder.prune_hubs(g, 99.0)
    orphans = graph_builder.drop_isolated(g)
    assert orphans == {f"leaf{i}" for i in range(SPOKES)}
    assert set(g.nodes) == {"x", "y"}


def test_summarise_reports_the_finished_shape():
    g = nx.path_graph(5)  # degrees: 1,2,2,2,1
    stats = graph_builder.summarise(
        g, hubs_removed=3, isolated_removed=7, hub_degree_cutoff=9
    )
    assert stats.nodes == 5
    assert stats.edges == 4
    assert stats.max_degree == 2
    assert stats.median_degree == 2
    assert stats.hubs_removed == 3
    assert stats.isolated_removed == 7
    assert stats.hub_degree_cutoff == 9


def test_summarise_handles_an_empty_graph():
    stats = graph_builder.summarise(
        nx.Graph(), hubs_removed=0, isolated_removed=0, hub_degree_cutoff=0
    )
    assert stats.nodes == 0
    assert stats.mean_degree == 0.0


# --------------------------------------------------------------------------
# End-to-end over the committed fixture
# --------------------------------------------------------------------------


def test_fixture_produces_the_expected_graph(sample_csv, sample_vocab):
    """Parser + builder together, on real ConceptNet-shaped input."""
    loader = ConceptNetLoader(
        path=sample_csv,
        relation_filter=is_allowed,
        concept_filter=sample_vocab.__contains__,
    )
    g = graph_builder.build(loader, sample_vocab, min_weight=1.0)

    assert set(g.nodes) == {"apple", "newton", "gravity", "moon", "tide", "ocean", "pie"}
    assert set(map(frozenset, g.edges)) == {
        frozenset({"apple", "newton"}),
        frozenset({"newton", "gravity"}),
        frozenset({"gravity", "moon"}),
        frozenset({"moon", "tide"}),
        frozenset({"tide", "ocean"}),
        frozenset({"apple", "pie"}),
        frozenset({"ocean", "moon"}),
    }

    # `orbit` had one edge at weight 0.5, below the threshold: no edge, so the
    # node never enters the graph at all.
    assert "orbit" not in g

    # apple->pie arrives twice: RelatedTo at 1.5 and UsedFor at 2.0.
    assert g["apple"]["pie"]["weight"] == pytest.approx(2.0)
    assert g["apple"]["pie"]["relations"] == ("RelatedTo", "UsedFor")
