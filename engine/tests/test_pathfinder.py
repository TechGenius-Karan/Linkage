"""Path constraints and bidirectional search (planning.md 7.4)."""

from __future__ import annotations

import random

import networkx as nx
import pytest
from dataclasses import replace

from linkage_engine.config import Config
from linkage_engine.domain.models import Path
from linkage_engine.domain.pathfinder import (
    BidirectionalBFSFinder,
    chord_pairs,
    edge_attributes,
    has_chord,
    has_direct_se_edge,
)

CFG = Config(min_edge_weight=2.0, min_endpoint_degree=1, max_paths_per_pair=8)


def line(*words: str, weight: float = 2.5) -> nx.Graph:
    g = nx.Graph()
    for a, b in zip(words, words[1:]):
        g.add_edge(a, b, weight=weight, relations=("RelatedTo",))
    return g


CHAIN = ("s", "w1", "w2", "w3", "w4", "e")


# --------------------------------------------------------------------------
# Constraint predicates
# --------------------------------------------------------------------------


def test_chord_pairs_excludes_path_edges_and_the_endpoint_pair():
    pairs = chord_pairs(6)
    # C(6,2)=15, minus 5 path edges, minus the start/end pair = 9.
    assert len(pairs) == 9
    assert (0, 5) not in pairs  # handled by has_direct_se_edge
    for i, j in pairs:
        assert j - i > 1


def test_direct_start_end_edge_is_detected():
    g = line(*CHAIN)
    assert not has_direct_se_edge(g, CHAIN)
    g.add_edge("s", "e", weight=2.0)
    assert has_direct_se_edge(g, CHAIN)


def test_clean_chain_has_no_chord():
    assert not has_chord(line(*CHAIN), CHAIN)


@pytest.mark.parametrize("a, b", [("s", "w2"), ("s", "w3"), ("w1", "w3"), ("w2", "w4"), ("w1", "e")])
def test_any_shortcut_counts_as_a_chord(a, b):
    g = line(*CHAIN)
    g.add_edge(a, b, weight=2.0)
    assert has_chord(g, CHAIN)


def test_start_end_edge_is_not_reported_as_a_chord():
    """It is banned, but by `has_direct_se_edge` -- keeping the two separate
    is what lets `diagnose` attribute rejections to the right stage."""
    g = line(*CHAIN)
    g.add_edge("s", "e", weight=2.0)
    assert not has_chord(g, CHAIN)


def test_edge_attributes_reads_weights_in_path_order():
    g = nx.Graph()
    g.add_edge("a", "b", weight=1.0, relations=("IsA",))
    g.add_edge("b", "c", weight=2.0, relations=("UsedFor", "RelatedTo"))
    weights, relations = edge_attributes(g, ("a", "b", "c"))
    assert weights == (1.0, 2.0)
    assert relations == (("IsA",), ("UsedFor", "RelatedTo"))


# --------------------------------------------------------------------------
# The finder
# --------------------------------------------------------------------------


def test_finds_the_obvious_chain():
    finder = BidirectionalBFSFinder(line(*CHAIN), CFG, random.Random(0))
    paths = finder.paths_between("s", "e")
    assert len(paths) == 1
    assert paths[0].steps == ("w1", "w2", "w3", "w4")
    assert paths[0].start == "s" and paths[0].end == "e"


def test_rejects_a_pair_joined_by_a_direct_edge():
    g = line(*CHAIN)
    g.add_edge("s", "e", weight=3.0)
    finder = BidirectionalBFSFinder(g, CFG, random.Random(0))
    assert finder.paths_between("s", "e") == []


def test_rejects_a_chain_with_a_shortcut():
    g = line(*CHAIN)
    g.add_edge("w1", "w3", weight=3.0)
    finder = BidirectionalBFSFinder(g, CFG, random.Random(0))
    assert finder.paths_between("s", "e") == []


def test_chordless_can_be_switched_off():
    g = line(*CHAIN)
    g.add_edge("w1", "w3", weight=3.0)
    finder = BidirectionalBFSFinder(
        g, replace(CFG, enforce_chordless=False), random.Random(0)
    )
    assert finder.paths_between("s", "e")


def test_rejects_a_chain_whose_weakest_edge_is_too_light():
    g = line(*CHAIN)
    g["w2"]["w3"]["weight"] = 0.5
    finder = BidirectionalBFSFinder(g, CFG, random.Random(0))
    assert finder.paths_between("s", "e") == []


def test_gates_on_the_weakest_edge_not_the_average():
    """Four strong rungs must not carry one weak one (planning.md 7.4)."""
    g = line(*CHAIN, weight=9.0)
    g["w2"]["w3"]["weight"] = 1.0
    finder = BidirectionalBFSFinder(g, CFG, random.Random(0))
    assert finder.paths_between("s", "e") == []


def test_same_node_endpoints_yield_nothing():
    finder = BidirectionalBFSFinder(line(*CHAIN), CFG, random.Random(0))
    assert finder.paths_between("s", "s") == []


def test_respects_the_per_pair_budget():
    """Risk #20: 25 seeds produced 33M paths, so this bound is load-bearing."""
    g = nx.Graph()
    # Many parallel 5-edge routes between s and e.
    for i in range(12):
        for a, b in zip(("s", f"a{i}", f"b{i}", f"c{i}", f"d{i}", "e"),
                        (f"a{i}", f"b{i}", f"c{i}", f"d{i}", "e")):
            g.add_edge(a, b, weight=3.0, relations=("RelatedTo",))
    cfg = replace(CFG, max_paths_per_pair=3)
    finder = BidirectionalBFSFinder(g, cfg, random.Random(0))
    assert len(finder.paths_between("s", "e")) == 3


def test_endpoints_below_the_degree_floor_are_excluded():
    g = line(*CHAIN)
    g.add_edge("lonely", "s", weight=3.0)  # degree 1
    finder = BidirectionalBFSFinder(
        g, replace(CFG, min_endpoint_degree=2), random.Random(0)
    )
    assert "lonely" not in finder.endpoints


def test_raises_when_no_endpoints_qualify():
    g = nx.Graph()
    g.add_edge("a", "b", weight=1.0)
    with pytest.raises(ValueError, match="nothing to search between"):
        BidirectionalBFSFinder(g, Config(min_endpoint_degree=99), random.Random(0))


def test_find_is_reproducible_for_a_fixed_seed():
    """planning.md 7.8: same seed, same puzzles, every run."""
    g = nx.gnp_random_graph(60, 0.12, seed=7)
    g = nx.relabel_nodes(g, {i: f"w{i}" for i in g.nodes})
    nx.set_edge_attributes(g, 3.0, "weight")
    nx.set_edge_attributes(g, ("RelatedTo",), "relations")

    def run():
        finder = BidirectionalBFSFinder(g, CFG, random.Random(99))
        return [p.nodes for p in finder.find(budget=15)]

    assert run() == run()


def test_funnel_counters_attribute_each_rejection():
    g = line(*CHAIN)
    g.add_edge("w1", "w3", weight=3.0)  # a chord
    finder = BidirectionalBFSFinder(g, CFG, random.Random(0))
    finder.paths_between("s", "e")
    assert finder.counts.paths_found >= 1
    assert finder.counts.no_se_edge >= 1
    assert finder.counts.chordless == 0  # died at the chord stage


def test_rejects_a_chain_whose_step_echoes_an_endpoint():
    """Found by reading real output: `STICK -> ... sticks ... -> SCREAM`.

    The FormOf/DerivedFrom blocklist removes morphological *edges*, but two
    kin words can still be joined by an ordinary RelatedTo -- so the rule has
    to be re-applied to the assembled chain, not just to the graph.
    """
    from linkage_engine.data.stemming import PorterStemmerAdapter

    g = line("stick", "w1", "sticks", "w3", "w4", "scream")
    finder = BidirectionalBFSFinder(g, CFG, random.Random(0), PorterStemmerAdapter())
    assert finder.paths_between("stick", "scream") == []


def test_rejects_a_chain_whose_steps_echo_each_other():
    from linkage_engine.data.stemming import PorterStemmerAdapter

    g = line("s", "running", "w2", "run", "w4", "e")
    finder = BidirectionalBFSFinder(g, CFG, random.Random(0), PorterStemmerAdapter())
    assert finder.paths_between("s", "e") == []


def test_stem_collisions_are_the_only_thing_rejecting_that_chain():
    """With an exact-match stemmer the same chain is fine, which proves the
    rejection above comes from stemming and not some unrelated constraint."""
    g = line("stick", "w1", "sticks", "w3", "w4", "scream")
    finder = BidirectionalBFSFinder(g, CFG, random.Random(0))  # exact-match
    assert len(finder.paths_between("stick", "scream")) == 1


def test_exact_repeats_are_rejected_even_without_a_real_stemmer():
    g = line(*CHAIN)
    finder = BidirectionalBFSFinder(g, CFG, random.Random(0))
    assert finder._build(("s", "w1", "w1", "w3", "w4", "e")) is None


def test_path_model_rejects_inconsistent_edge_counts():
    with pytest.raises(ValueError, match="needs 5 edges"):
        Path(start="s", end="e", steps=("a", "b", "c", "d"), weights=(1.0,), relations=())
