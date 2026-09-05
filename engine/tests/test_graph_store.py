"""Persistence and provenance (planning.md 7.2, 7.8)."""

from __future__ import annotations

import pickle

import networkx as nx
import pytest

from linkage_engine.config import Config
from linkage_engine.data import graph_store


@pytest.fixture
def graph():
    g = nx.Graph()
    g.add_edge("apple", "newton", weight=2.4, relations=("RelatedTo",))
    g.add_edge("newton", "gravity", weight=3.1, relations=("RelatedTo",))
    return g


@pytest.fixture
def cfg(tmp_path):
    return Config(repo_root=tmp_path)


def test_networkx_no_longer_ships_gpickle_helpers():
    """The gotcha from planning.md 7.2, pinned as a test.

    `write_gpickle`/`read_gpickle` were removed in NetworkX 3.0. If a future
    bump ever restores them, this fails and we can reconsider -- until then
    it documents why we pickle by hand.
    """
    assert not hasattr(nx, "write_gpickle")
    assert not hasattr(nx, "read_gpickle")


def test_roundtrip_preserves_topology_and_attributes(graph, cfg):
    meta = graph_store.build_meta(cfg, conceptnet_sha256="abc123", vocab_size=42)
    graph_store.save(graph, cfg.graph_path, meta)

    loaded = graph_store.load(cfg.graph_path)
    assert set(loaded.nodes) == set(graph.nodes)
    assert loaded["apple"]["newton"]["weight"] == pytest.approx(2.4)
    assert loaded["apple"]["newton"]["relations"] == ("RelatedTo",)


def test_metadata_is_stamped_onto_the_graph(graph, cfg):
    meta = graph_store.build_meta(cfg, conceptnet_sha256="abc123", vocab_size=42)
    graph_store.save(graph, cfg.graph_path, meta)

    loaded = graph_store.load(cfg.graph_path)
    assert loaded.graph["conceptnet_sha256"] == "abc123"
    assert loaded.graph["vocab_size"] == 42
    assert loaded.graph["config_fingerprint"] == cfg.fingerprint()
    for key in ("wordfreq_version", "networkx_version", "built_at", "meta_version"):
        assert loaded.graph[key]


def test_extra_metadata_is_merged(graph, cfg):
    meta = graph_store.build_meta(
        cfg, conceptnet_sha256="x", vocab_size=1, extra={"hub_degree_cutoff": 77}
    )
    graph_store.save(graph, cfg.graph_path, meta)
    assert graph_store.load(cfg.graph_path).graph["hub_degree_cutoff"] == 77


def test_save_uses_pickle_protocol_5(graph, cfg):
    meta = graph_store.build_meta(cfg, conceptnet_sha256="x", vocab_size=1)
    graph_store.save(graph, cfg.graph_path, meta)
    header = cfg.graph_path.read_bytes()[:2]
    assert header == pickle.PROTO + bytes([graph_store.PICKLE_PROTOCOL])


def test_save_leaves_no_part_file_behind(graph, cfg):
    meta = graph_store.build_meta(cfg, conceptnet_sha256="x", vocab_size=1)
    graph_store.save(graph, cfg.graph_path, meta)
    assert not list(cfg.data_dir.glob("*.part"))


def test_load_gives_an_actionable_error_when_missing(cfg):
    with pytest.raises(FileNotFoundError, match="linkage build-graph"):
        graph_store.load(cfg.graph_path)


def test_load_rejects_a_pickle_that_is_not_a_graph(cfg):
    cfg.graph_path.parent.mkdir(parents=True, exist_ok=True)
    with cfg.graph_path.open("wb") as fh:
        pickle.dump({"not": "a graph"}, fh)
    with pytest.raises(TypeError, match="networkx Graph"):
        graph_store.load(cfg.graph_path)


# --------------------------------------------------------------------------
# Fingerprinting
# --------------------------------------------------------------------------


def test_fingerprint_is_stable_across_instances():
    assert Config().fingerprint() == Config().fingerprint()


def test_fingerprint_ignores_machine_specific_paths(tmp_path):
    """repo_root differs per machine and must not change the fingerprint."""
    assert Config(repo_root=tmp_path).fingerprint() == Config().fingerprint()


@pytest.mark.parametrize(
    "field, value",
    [
        ("vocab_fetch_n", 999),
        ("vocab_target", 999),
        ("vocab_min_rank", 1),
        ("hub_percentile", 95.0),
        ("min_graph_edge_weight", 2.0),
        ("word_max_len", 20),
        ("conceptnet_url", "https://example.invalid/dump.gz"),
    ],
)
def test_fingerprint_changes_when_a_graph_affecting_knob_changes(field, value):
    from dataclasses import replace

    assert replace(Config(), **{field: value}).fingerprint() != Config().fingerprint()


@pytest.mark.parametrize(
    "field, value",
    [
        ("bank_size", 12),
        ("chain_length", 5),
        ("min_edge_weight", 3.0),
        ("enforce_chordless", False),
        ("target_approved", 100),
        ("seed", 1),
        ("epoch_date", "2030-01-01"),
    ],
)
def test_fingerprint_ignores_knobs_the_graph_cannot_see(field, value):
    """A warning that fires when nothing is wrong is a warning people learn
    to ignore. Puzzle shape and search budgets are consumed downstream and
    leave the built graph untouched, so they must not invalidate it."""
    from dataclasses import replace

    assert replace(Config(), **{field: value}).fingerprint() == Config().fingerprint()


def test_every_graph_affecting_field_exists_on_config():
    """Guards against a rename silently dropping a field from the hash."""
    from dataclasses import asdict

    from linkage_engine.config import GRAPH_AFFECTING_FIELDS

    assert GRAPH_AFFECTING_FIELDS <= set(asdict(Config()))


def test_check_fingerprint_accepts_a_matching_graph(graph, cfg):
    meta = graph_store.build_meta(cfg, conceptnet_sha256="x", vocab_size=1)
    graph_store.save(graph, cfg.graph_path, meta)
    assert graph_store.check_fingerprint(graph_store.load(cfg.graph_path), cfg) is None


def test_check_fingerprint_flags_a_stale_graph(graph, cfg):
    from dataclasses import replace

    meta = graph_store.build_meta(cfg, conceptnet_sha256="x", vocab_size=1)
    graph_store.save(graph, cfg.graph_path, meta)

    changed = replace(cfg, hub_percentile=90.0)
    warning = graph_store.check_fingerprint(graph_store.load(cfg.graph_path), changed)
    assert warning and "build-graph --force" in warning


def test_check_fingerprint_flags_an_unstamped_graph(cfg):
    assert "no config fingerprint" in graph_store.check_fingerprint(nx.Graph(), cfg)
