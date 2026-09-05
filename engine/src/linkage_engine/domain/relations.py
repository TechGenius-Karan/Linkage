"""Which ConceptNet relations produce a genuine conceptual leap.

Domain tier: pure. This is where puzzle quality is won or lost
(planning.md 7.2).

The operative mechanism is the ALLOWLIST -- an unknown relation is rejected by
default, which is the safe direction. BLOCKED_WITH_REASON is documentation of
intent, and `test_relations.py` asserts the two never disagree.
"""

from __future__ import annotations

from types import MappingProxyType

#: Associations we want. Each of these can carry a chain from one idea to the
#: next in a way a person would recognise as a leap rather than a definition.
ALLOWLIST: frozenset[str] = frozenset(
    {
        "RelatedTo",
        "IsA",
        "PartOf",
        "HasA",
        "UsedFor",
        "CapableOf",
        "AtLocation",
        "Causes",
        "HasProperty",
        "MadeOf",
        "SymbolOf",
        "MotivatedByGoal",
    }
)

#: Relations we deliberately exclude, and why. Kept as data rather than prose
#: so the reasoning is testable and survives refactoring.
BLOCKED_WITH_REASON: MappingProxyType[str, str] = MappingProxyType(
    {
        "FormOf": "Morphological, not conceptual. run -> running is a suffix, not an aha.",
        "DerivedFrom": "Morphological, not conceptual.",
        "EtymologicallyRelatedTo": "Morphological, not conceptual.",
        "EtymologicallyDerivedFrom": "Morphological, not conceptual.",
        "Synonym": "The leap is too small. Zero insight.",
        "SimilarTo": "The leap is too small. Zero insight.",
        "Antonym": "Reads as a mistake to the player, not a connection.",
        "DistinctFrom": "Reads as a mistake to the player, not a connection.",
        "NotUsedFor": "Negations invert the semantics of the whole chain.",
        "NotCapableOf": "Negations invert the semantics of the whole chain.",
        "NotHasProperty": "Negations invert the semantics of the whole chain.",
        "NotDesires": "Negations invert the semantics of the whole chain.",
        "ExternalURL": "Not conceptual data at all.",
        "HasContext": "Register/domain labels, not associations. Very noisy.",
        "DefinedAs": "Dictionary definition, not lateral association.",
    }
)


def relation_name(uri: str) -> str:
    """`/r/RelatedTo` -> `RelatedTo`; `/r/dbpedia/genre` -> `dbpedia/genre`.

    Namespaced relations keep their namespace so they can never collide with
    an allowlisted bare name.
    """
    return uri[3:] if uri.startswith("/r/") else uri


def is_allowed(uri: str) -> bool:
    """True when this relation may contribute an edge to the graph."""
    return relation_name(uri) in ALLOWLIST
