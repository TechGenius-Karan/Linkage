"""Candidate assembly (planning.md 7.6, 7.7).

The generator composes pathfinder + distractors + scorer. It owns no rules of
its own, so these tests are about orchestration: budgets, one-puzzle-per-pair,
and reproducibility.

The full-graph determinism check (generate twice, diff the bytes) is a
four-minute run and lives in the release checklist, not here. This file pins
the same property on a synthetic graph in milliseconds.
"""

from __future__ import annotations

import random
from dataclasses import replace

import networkx as nx
import pytest

from linkage_engine.config import Config
from linkage_engine.data.stemming import IdentityStemmer
from linkage_engine.domain.distractors import DistractorSelector
from linkage_engine.domain.generator import CandidateGenerator, shuffled_bank
from linkage_engine.domain.scoring import QualityScorer
from linkage_engine.domain.validator import is_uniquely_solvable

CFG = Config(
    bank_size=8,
    bank_size_min=6,
    min_edge_weight=2.0,
    min_endpoint_degree=1,
    max_paths_per_pair=4,
    distractor_pool_size=40,
)


def toy_graph(chains: int = 6) -> nx.Graph:
    """Several disjoint 5-edge chains plus dead ends to draw distractors from."""
    g = nx.Graph()
    for c in range(chains):
        nodes = (f"s{c}", f"a{c}", f"b{c}", f"d{c}", f"f{c}", f"e{c}")
        for x, y in zip(nodes, nodes[1:]):
            g.add_edge(x, y, weight=3.0, relations=("RelatedTo",))
        for i in range(14):
            g.add_edge(f"b{c}", f"x{c}_{i}", weight=2.0 + i / 100, relations=("RelatedTo",))
    return g


def make_generator(graph, seed: int = 1, cfg: Config = CFG) -> CandidateGenerator:
    return CandidateGenerator(
        graph, cfg, random.Random(seed), DistractorSelector(cfg, IdentityStemmer()), QualityScorer()
    )


# --------------------------------------------------------------------------
# Bank shuffling
# --------------------------------------------------------------------------


def test_shuffled_bank_preserves_membership():
    bank = ("a", "b", "c", "d", "e")
    assert set(shuffled_bank(bank, 42)) == set(bank)
    assert len(shuffled_bank(bank, 42)) == len(bank)


def test_shuffled_bank_is_stable_for_a_seed():
    """Tile positions must not move between refreshes (planning.md 2.3)."""
    bank = tuple("abcdefghijk")
    assert shuffled_bank(bank, 7) == shuffled_bank(bank, 7)


def test_shuffled_bank_differs_across_seeds():
    bank = tuple("abcdefghijk")
    assert shuffled_bank(bank, 1) != shuffled_bank(bank, 2)


def test_shuffled_bank_actually_shuffles():
    """A sorted bank would leak the solution: its words would cluster."""
    bank = tuple("abcdefghijk")
    assert any(shuffled_bank(bank, s) != bank for s in range(10))


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------


def test_emits_candidates_that_are_uniquely_solvable():
    g = toy_graph()
    gen = make_generator(g)
    produced = list(gen.generate(wanted=4, max_pairs=200))
    assert produced
    for candidate in produced:
        assert is_uniquely_solvable(
            g, candidate.path.start, candidate.path.end, candidate.bank, CFG.chain_length
        )


def test_bank_always_contains_the_solution():
    gen = make_generator(toy_graph())
    for candidate in gen.generate(wanted=4, max_pairs=200):
        assert set(candidate.solution).issubset(candidate.bank)


def test_distractors_exclude_the_solution():
    gen = make_generator(toy_graph())
    for candidate in gen.generate(wanted=4, max_pairs=200):
        assert not set(candidate.distractors) & set(candidate.solution)
        assert len(candidate.distractors) == len(candidate.bank) - CFG.chain_length


def test_respects_the_wanted_count():
    gen = make_generator(toy_graph())
    assert len(list(gen.generate(wanted=2, max_pairs=500))) == 2


def test_respects_the_pair_budget():
    """Risk #20 -- the run must end even when nothing is being found."""
    empty = nx.Graph()
    for i in range(40):
        empty.add_edge(f"n{i}", f"m{i}", weight=3.0, relations=("RelatedTo",))
    gen = make_generator(empty)
    assert list(gen.generate(wanted=99, max_pairs=25)) == []
    assert gen.counts.pairs_sampled <= 25


def test_never_emits_two_puzzles_for_one_endpoint_pair():
    """planning.md 7.7.1 forbids duplicate (start, end) across the year, so
    emitting several per pair would only queue work export must reject."""
    gen = make_generator(toy_graph())
    produced = list(gen.generate(wanted=20, max_pairs=400))
    pairs = [frozenset({c.path.start, c.path.end}) for c in produced]
    assert len(set(pairs)) == len(pairs)


def test_candidates_carry_a_score_breakdown():
    """When the queue fills with bad puzzles this is the only way to see
    which component is mis-weighted."""
    gen = make_generator(toy_graph())
    candidate = next(iter(gen.generate(wanted=1, max_pairs=200)))
    assert dict(candidate.score_breakdown)
    assert 0.0 <= candidate.quality <= 1.0


def test_generation_is_byte_for_byte_reproducible():
    """planning.md 7.8. The real check regenerates the full archive and diffs
    it; this pins the same property fast enough to run on every commit."""
    g = toy_graph()

    def run():
        return [
            (c.path.nodes, c.bank, c.quality)
            for c in make_generator(g, seed=99).generate(wanted=5, max_pairs=300)
        ]

    assert run() == run()


def test_a_different_seed_finds_different_puzzles():
    """Budget is generous on purpose: the toy graph is a handful of disjoint
    chains, so a randomly sampled endpoint pair usually straddles two
    components and finds nothing. That is a property of the fixture, not of
    the generator -- the real graph is 99.9% one component.
    """
    g = toy_graph(chains=6)
    a = [c.path.nodes for c in make_generator(g, seed=1).generate(wanted=5, max_pairs=3000)]
    b = [c.path.nodes for c in make_generator(g, seed=2).generate(wanted=5, max_pairs=3000)]
    assert a and b, "fixture produced nothing; raise the budget"
    assert a != b


def test_counts_are_reported_for_diagnose():
    gen = make_generator(toy_graph())
    list(gen.generate(wanted=3, max_pairs=200))
    assert gen.counts.pairs_sampled > 0
    assert gen.counts.paths_found > 0
    assert gen.counts.unique_bank > 0


def test_drops_candidates_when_no_safe_bank_can_be_built():
    """Risk #16: a thin bank is worse than one fewer puzzle."""
    bare = nx.Graph()
    nodes = ("s", "a", "b", "c", "d", "e")
    for x, y in zip(nodes, nodes[1:]):
        bare.add_edge(x, y, weight=3.0, relations=("RelatedTo",))
    gen = make_generator(bare, cfg=replace(CFG, bank_size=8, bank_size_min=8))
    assert list(gen.generate(wanted=5, max_pairs=100)) == []
