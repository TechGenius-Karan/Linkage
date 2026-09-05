"""Streaming ConceptNet parser (planning.md 7.2)."""

from __future__ import annotations

import pytest

from linkage_engine.data.conceptnet import (
    ConceptNetLoader,
    parse_concept,
    sha256_of,
    verify_cached,
)
from linkage_engine.domain.relations import is_allowed


@pytest.mark.parametrize(
    "uri, expected",
    [
        ("/c/en/apple", "apple"),
        ("/c/en/apple/n", "apple"),
        ("/c/en/apple/n/wn/food", "apple"),
        ("/c/fr/pomme", None),  # non-English
        ("/c/en/ice_cream", None),  # multiword
        ("/c/en/", None),  # empty lemma
        ("/c/de/apfel", None),
        ("garbage", None),
    ],
)
def test_parse_concept(uri, expected):
    assert parse_concept(uri) == expected


def _load(path, vocab):
    loader = ConceptNetLoader(
        path=path,
        relation_filter=is_allowed,
        concept_filter=vocab.__contains__,
    )
    return list(loader), loader.counters


def test_parses_only_the_assertions_we_want(sample_csv, sample_vocab):
    assertions, counters = _load(sample_csv, sample_vocab)

    pairs = {(a.start, a.end) for a in assertions}
    assert pairs == {
        ("apple", "newton"),
        ("newton", "gravity"),
        ("gravity", "moon"),
        ("moon", "tide"),
        ("tide", "ocean"),
        ("apple", "pie"),  # twice, via RelatedTo and UsedFor
        ("ocean", "moon"),
        ("apple", "orbit"),  # weak edge -- dropped later, by the graph builder
        ("apple", "apple"),  # self-loop -- likewise
    }
    assert counters.kept == 10


def test_gzip_and_plain_produce_identical_results(sample_csv, sample_csv_gz, sample_vocab):
    plain, _ = _load(sample_csv, sample_vocab)
    gzipped, _ = _load(sample_csv_gz, sample_vocab)
    assert plain == gzipped


def test_rejections_are_attributed_to_the_right_bucket(sample_csv, sample_vocab):
    _, c = _load(sample_csv, sample_vocab)

    assert c.malformed == 1  # the short line
    assert c.rejected_relation == 3  # Antonym, FormOf, dbpedia/genre
    assert c.rejected_concept == 2  # /c/fr/pomme, ice_cream
    assert c.rejected_filter == 1  # zzzunknown, outside the vocabulary
    assert c.lines == c.kept + c.malformed + (
        c.rejected_relation + c.rejected_concept + c.rejected_filter
    )


def test_weights_are_read_from_the_metadata_json(sample_csv, sample_vocab):
    assertions, _ = _load(sample_csv, sample_vocab)
    by_pair = {(a.start, a.end, a.relation): a.weight for a in assertions}
    assert by_pair[("apple", "newton", "RelatedTo")] == pytest.approx(2.4)
    assert by_pair[("newton", "gravity", "RelatedTo")] == pytest.approx(3.1)


def test_parser_does_not_do_the_graph_builders_job(sample_csv, sample_vocab):
    """Single Responsibility: the parser reports what the file says.

    Self-loops and sub-threshold weights are structural decisions about the
    *graph*, so they are dropped in `graph_builder`, not here. If this test
    ever fails because the parser started filtering them, two modules now
    share one responsibility and the weight threshold has two homes.
    """
    assertions, _ = _load(sample_csv, sample_vocab)

    weak = [a for a in assertions if a.end == "orbit"]
    assert weak and weak[0].weight == pytest.approx(0.5)

    assert any(a.start == a.end == "apple" for a in assertions)


def test_relation_prefix_is_stripped(sample_csv, sample_vocab):
    assertions, _ = _load(sample_csv, sample_vocab)
    assert all(not a.relation.startswith("/r/") for a in assertions)
    assert {"RelatedTo", "IsA", "AtLocation", "Causes", "UsedFor", "SymbolOf"} >= {
        a.relation for a in assertions
    }


def test_max_lines_stops_early(sample_csv, sample_vocab):
    loader = ConceptNetLoader(
        path=sample_csv,
        relation_filter=is_allowed,
        concept_filter=sample_vocab.__contains__,
        max_lines=3,
    )
    assertions = list(loader)
    assert loader.counters.lines == 3
    assert len(assertions) == 3


def test_progress_callback_is_optional_and_never_required(sample_csv, sample_vocab):
    seen: list[int] = []
    loader = ConceptNetLoader(
        path=sample_csv,
        relation_filter=is_allowed,
        concept_filter=sample_vocab.__contains__,
        progress=seen.append,
    )
    list(loader)
    # Fixture is far shorter than PROGRESS_EVERY, so it never fires -- the
    # point is that supplying a callback does not change the output.
    assert seen == []


def test_sha256_and_verify_roundtrip(tmp_path):
    target = tmp_path / "blob.bin"
    target.write_bytes(b"linkage")

    digest = sha256_of(target)
    assert len(digest) == 64

    # First call records a sidecar; second verifies against it.
    assert verify_cached(target) == digest
    assert (tmp_path / "blob.bin.sha256").read_text().strip() == digest
    assert verify_cached(target) == digest


def test_verify_cached_rejects_a_tampered_file(tmp_path):
    target = tmp_path / "blob.bin"
    target.write_bytes(b"linkage")
    verify_cached(target)

    target.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="mismatch"):
        verify_cached(target)


def test_verify_cached_honours_an_explicit_pin(tmp_path):
    target = tmp_path / "blob.bin"
    target.write_bytes(b"linkage")
    with pytest.raises(ValueError, match="mismatch"):
        verify_cached(target, expected_sha256="0" * 64)
