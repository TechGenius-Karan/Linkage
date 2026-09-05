"""Relation policy (planning.md 7.2).

The allowlist is the mechanism; the blocklist is documented intent. These
tests exist so the two can never silently disagree.
"""

from __future__ import annotations

import pytest

from linkage_engine.domain.relations import (
    ALLOWLIST,
    BLOCKED_WITH_REASON,
    is_allowed,
    relation_name,
)


def test_allowlist_and_blocklist_never_overlap():
    assert not (ALLOWLIST & BLOCKED_WITH_REASON.keys())


def test_every_blocked_relation_has_a_reason():
    for relation, reason in BLOCKED_WITH_REASON.items():
        assert reason.strip(), f"{relation} is blocked without a stated reason"


@pytest.mark.parametrize(
    "uri, expected",
    [
        ("/r/RelatedTo", "RelatedTo"),
        ("/r/IsA", "IsA"),
        ("/r/dbpedia/genre", "dbpedia/genre"),
        ("RelatedTo", "RelatedTo"),
    ],
)
def test_relation_name_strips_prefix(uri, expected):
    assert relation_name(uri) == expected


@pytest.mark.parametrize("relation", sorted(ALLOWLIST))
def test_allowlisted_relations_pass(relation):
    assert is_allowed(f"/r/{relation}")


@pytest.mark.parametrize("relation", sorted(BLOCKED_WITH_REASON))
def test_blocked_relations_are_rejected(relation):
    assert not is_allowed(f"/r/{relation}")


def test_namespaced_relations_cannot_collide_with_an_allowed_name():
    """`/r/dbpedia/genre` must not slip through by matching some bare name."""
    assert not is_allowed("/r/dbpedia/genre")
    assert not is_allowed("/r/dbpedia/RelatedTo")


def test_unknown_relations_are_rejected_by_default():
    """Allowlist semantics: an unrecognised relation fails closed."""
    assert not is_allowed("/r/SomeRelationInventedNextYear")
