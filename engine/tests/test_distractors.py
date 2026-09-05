"""Distractor strategies and bank construction (planning.md 7.6)."""

from __future__ import annotations

from dataclasses import replace

import networkx as nx
import pytest

from linkage_engine.config import Config
from linkage_engine.data.stemming import IdentityStemmer, PorterStemmerAdapter
from linkage_engine.domain.distractors import (
    DistractorSelector,
    NearMissStrategy,
    SemanticFieldStrategy,
    SiblingStrategy,
    overlaps_substring,
    shares_stem,
)
from linkage_engine.domain.models import Path
from linkage_engine.domain.validator import is_uniquely_solvable

CFG = Config(bank_size=8, bank_size_min=6, distractor_pool_size=50)


def make_path(g: nx.Graph, nodes=("s", "w1", "w2", "w3", "w4", "e")) -> Path:
    weights, relations = [], []
    for a, b in zip(nodes, nodes[1:]):
        weights.append(g[a][b]["weight"])
        relations.append(tuple(g[a][b].get("relations", ())))
    return Path(nodes[0], nodes[-1], nodes[1:-1], tuple(weights), tuple(relations))


@pytest.fixture
def chain_graph():
    g = nx.Graph()
    nodes = ("s", "w1", "w2", "w3", "w4", "e")
    for a, b in zip(nodes, nodes[1:]):
        g.add_edge(a, b, weight=3.0, relations=("RelatedTo",))
    return g


# --------------------------------------------------------------------------
# Strategies
# --------------------------------------------------------------------------


def test_near_miss_finds_dead_ends_beside_the_solution(chain_graph):
    chain_graph.add_edge("w2", "decoy", weight=2.5, relations=("RelatedTo",))
    proposals = NearMissStrategy().propose(chain_graph, make_path(chain_graph), 10)
    assert [p.word for p in proposals] == ["decoy"]
    assert proposals[0].source == "near-miss"


def test_near_miss_never_proposes_a_word_already_on_the_path(chain_graph):
    proposals = NearMissStrategy().propose(chain_graph, make_path(chain_graph), 10)
    assert not {p.word for p in proposals} & set(make_path(chain_graph).nodes)


def test_sibling_finds_words_sharing_an_isa_parent(chain_graph):
    chain_graph.add_edge("w1", "bird", weight=3.0, relations=("IsA",))
    chain_graph.add_edge("robin", "bird", weight=2.8, relations=("IsA",))
    proposals = SiblingStrategy().propose(chain_graph, make_path(chain_graph), 10)
    assert "robin" in {p.word for p in proposals}


def test_sibling_ignores_non_isa_edges(chain_graph):
    chain_graph.add_edge("w1", "bird", weight=3.0, relations=("RelatedTo",))
    chain_graph.add_edge("robin", "bird", weight=2.8, relations=("RelatedTo",))
    assert SiblingStrategy().propose(chain_graph, make_path(chain_graph), 10) == []


def test_semantic_field_takes_words_near_the_anchors(chain_graph):
    chain_graph.add_edge("s", "nearstart", weight=2.9, relations=("RelatedTo",))
    proposals = SemanticFieldStrategy().propose(chain_graph, make_path(chain_graph), 10)
    assert "nearstart" in {p.word for p in proposals}


def test_semantic_field_excludes_words_touching_the_interior(chain_graph):
    """Otherwise it would double-count what NearMissStrategy already found."""
    chain_graph.add_edge("s", "bridging", weight=2.9, relations=("RelatedTo",))
    chain_graph.add_edge("bridging", "w3", weight=2.9, relations=("RelatedTo",))
    proposals = SemanticFieldStrategy().propose(chain_graph, make_path(chain_graph), 10)
    assert "bridging" not in {p.word for p in proposals}


def test_proposals_are_ranked_by_temptingness_then_name(chain_graph):
    for word, weight in [("low", 1.0), ("high", 9.0), ("beta", 5.0), ("alpha", 5.0)]:
        chain_graph.add_edge("w2", word, weight=weight, relations=("RelatedTo",))
    proposals = NearMissStrategy().propose(chain_graph, make_path(chain_graph), 10)
    assert [p.word for p in proposals] == ["high", "alpha", "beta", "low"]


# --------------------------------------------------------------------------
# Bank-level rejections
# --------------------------------------------------------------------------


def test_shares_stem_catches_morphological_kin():
    stemmer = PorterStemmerAdapter()
    assert shares_stem(stemmer, "moons", frozenset({"moon"}))
    assert shares_stem(stemmer, "sailing", frozenset({"sail"}))
    assert not shares_stem(stemmer, "ocean", frozenset({"moon"}))


def test_overlaps_substring_ignores_short_coincidences():
    assert not overlaps_substring("heart", frozenset({"art"}))  # 3 chars, fine
    assert overlaps_substring("starship", frozenset({"star"}))
    assert not overlaps_substring("ocean", frozenset({"apple"}))


# --------------------------------------------------------------------------
# The selector
# --------------------------------------------------------------------------


def _wide_graph():
    """A clean chain plus plenty of harmless dead ends to draw from."""
    g = nx.Graph()
    nodes = ("s", "w1", "w2", "w3", "w4", "e")
    for a, b in zip(nodes, nodes[1:]):
        g.add_edge(a, b, weight=3.0, relations=("RelatedTo",))
    for i in range(12):
        g.add_edge("w2", f"dead{i}", weight=2.0 + i / 100, relations=("RelatedTo",))
    return g


def test_bank_contains_the_solution_and_reaches_target_size():
    g = _wide_graph()
    selector = DistractorSelector(CFG, IdentityStemmer())
    bank = selector.build_bank(g, make_path(g))
    assert bank is not None
    assert set(("w1", "w2", "w3", "w4")).issubset(bank)
    assert len(bank) == CFG.bank_size


def test_bank_is_uniquely_solvable_by_construction():
    """The invariant the whole game rests on (planning.md 7.6)."""
    g = _wide_graph()
    selector = DistractorSelector(CFG, IdentityStemmer())
    bank = selector.build_bank(g, make_path(g))
    assert is_uniquely_solvable(g, "s", "e", bank, CFG.chain_length)


def test_a_distractor_that_would_create_a_second_solution_is_refused():
    g = _wide_graph()
    # x, y complete an alternate chain s -> x -> y -> w3 -> w4 -> e.
    g.add_edge("s", "x", weight=3.0, relations=("RelatedTo",))
    g.add_edge("x", "y", weight=3.0, relations=("RelatedTo",))
    g.add_edge("y", "w3", weight=3.0, relations=("RelatedTo",))

    selector = DistractorSelector(CFG, IdentityStemmer())
    bank = selector.build_bank(g, make_path(g))
    assert bank is not None
    # Admitting both x and y together would make the puzzle ambiguous.
    assert not {"x", "y"}.issubset(bank)
    assert is_uniquely_solvable(g, "s", "e", bank, CFG.chain_length)


def test_returns_none_when_too_few_safe_distractors_exist():
    """Risk #16: drop the candidate rather than ship a thin bank."""
    g = nx.Graph()
    nodes = ("s", "w1", "w2", "w3", "w4", "e")
    for a, b in zip(nodes, nodes[1:]):
        g.add_edge(a, b, weight=3.0, relations=("RelatedTo",))
    selector = DistractorSelector(CFG, IdentityStemmer())
    assert selector.build_bank(g, make_path(g)) is None


def test_falls_back_to_the_minimum_bank_size():
    g = _wide_graph()
    cfg = replace(CFG, bank_size=40, bank_size_min=6)
    selector = DistractorSelector(cfg, IdentityStemmer())
    bank = selector.build_bank(g, make_path(g))
    assert bank is not None and len(bank) >= cfg.bank_size_min


def test_stem_collisions_are_kept_out_of_one_bank():
    g = _wide_graph()
    g.add_edge("w2", "moon", weight=9.0, relations=("RelatedTo",))
    g.add_edge("w2", "moons", weight=8.9, relations=("RelatedTo",))
    selector = DistractorSelector(CFG, PorterStemmerAdapter())
    bank = selector.build_bank(g, make_path(g))
    assert bank is not None
    assert not {"moon", "moons"}.issubset(bank)


def test_a_decoy_may_not_share_a_stem_with_an_endpoint():
    """Found by reading real output: `IRELAND -> ... -> BRANCHES` shipped
    `branch` as a decoy, and `WALLS` shipped `wall`.

    The endpoints sit on screen for the whole game, so a decoy echoing one is
    more visible than two decoys echoing each other -- and the original check
    compared candidates against the bank only.
    """
    g = nx.Graph()
    nodes = ("s", "w1", "w2", "w3", "w4", "branches")
    for a, b in zip(nodes, nodes[1:]):
        g.add_edge(a, b, weight=3.0, relations=("RelatedTo",))
    for i in range(12):
        g.add_edge("w2", f"dead{i}", weight=2.0 + i / 100, relations=("RelatedTo",))
    g.add_edge("w2", "branch", weight=9.0, relations=("RelatedTo",))

    path = Path(
        "s", "branches", ("w1", "w2", "w3", "w4"), (3.0,) * 5, (("RelatedTo",),) * 5
    )
    bank = DistractorSelector(CFG, PorterStemmerAdapter()).build_bank(g, path)
    assert bank is not None
    assert "branch" not in bank


def test_a_decoy_may_not_be_a_substring_of_an_endpoint():
    g = nx.Graph()
    nodes = ("s", "w1", "w2", "w3", "w4", "starship")
    for a, b in zip(nodes, nodes[1:]):
        g.add_edge(a, b, weight=3.0, relations=("RelatedTo",))
    for i in range(12):
        g.add_edge("w2", f"dead{i}", weight=2.0 + i / 100, relations=("RelatedTo",))
    g.add_edge("w2", "star", weight=9.0, relations=("RelatedTo",))

    path = Path(
        "s", "starship", ("w1", "w2", "w3", "w4"), (3.0,) * 5, (("RelatedTo",),) * 5
    )
    bank = DistractorSelector(CFG, IdentityStemmer()).build_bank(g, path)
    assert bank is not None
    assert "star" not in bank


def test_consideration_order_spreads_across_bands():
    """Hardest-first ordering made every bank maximally confusing (95% of
    tiles wired to one side of a slot). The draw now mixes bands."""
    from linkage_engine.domain.distractors import ScoredWord

    pool = [ScoredWord(f"w{i}", 100.0 - i, "near-miss") for i in range(30)]
    order = DistractorSelector(CFG, IdentityStemmer()).consideration_order(pool)

    assert sorted(w.word for w in order) == sorted(w.word for w in pool)
    # The first cycle takes 3 hard, 2 medium, 1 easy -- so an easy-band word
    # must appear before the hard band is exhausted.
    first_six = [w.word for w in order[:6]]
    assert "w20" in first_six or "w21" in first_six, first_six
    assert order[0].word == "w0", "hardest candidate should still lead"


def test_consideration_order_leaves_tiny_pools_alone():
    from linkage_engine.domain.distractors import ScoredWord

    pool = [ScoredWord(f"w{i}", 10.0 - i, "near-miss") for i in range(4)]
    order = DistractorSelector(CFG, IdentityStemmer()).consideration_order(pool)
    assert [w.word for w in order] == [w.word for w in pool]


def test_consideration_order_is_deterministic():
    from linkage_engine.domain.distractors import ScoredWord

    pool = [ScoredWord(f"w{i}", 100.0 - i, "near-miss") for i in range(30)]
    sel = DistractorSelector(CFG, IdentityStemmer())
    assert [w.word for w in sel.consideration_order(pool)] == [
        w.word for w in sel.consideration_order(pool)
    ]


def test_build_bank_is_deterministic():
    g = _wide_graph()
    selector = DistractorSelector(CFG, IdentityStemmer())
    assert selector.build_bank(g, make_path(g)) == selector.build_bank(g, make_path(g))


def test_pool_merges_strategies_keeping_the_highest_score(chain_graph):
    """`cousin` is reachable two ways; the pool keeps the stronger score.

    Sibling scores it at min(3.0, 9.0) = 3.0 via the shared IsA parent.
    Near-miss scores it at 6.0 as a dead end off w2. 6.0 must win.
    """
    chain_graph.add_edge("w1", "parent", weight=3.0, relations=("IsA",))
    chain_graph.add_edge("cousin", "parent", weight=9.0, relations=("IsA",))
    chain_graph.add_edge("w2", "cousin", weight=6.0, relations=("RelatedTo",))

    selector = DistractorSelector(CFG, IdentityStemmer())
    pool = {p.word: p for p in selector.pool(chain_graph, make_path(chain_graph))}
    assert pool["cousin"].temptingness == pytest.approx(6.0)
    assert pool["cousin"].source == "near-miss"


def test_pool_is_sorted_best_first(chain_graph):
    for word, weight in [("weak", 1.0), ("strong", 8.0), ("mid", 4.0)]:
        chain_graph.add_edge("w3", word, weight=weight, relations=("RelatedTo",))
    selector = DistractorSelector(CFG, IdentityStemmer())
    words = [p.word for p in selector.pool(chain_graph, make_path(chain_graph))]
    assert words.index("strong") < words.index("mid") < words.index("weak")
