"""Vocabulary filter chain (planning.md 7.1, 3.1.1)."""

from __future__ import annotations

import pytest

from linkage_engine.config import Config
from linkage_engine.data.pos import AllowAllPosChecker
from linkage_engine.domain.filters import build_chain, first_rejecting, is_normalised
from linkage_engine.domain.wordlists import (
    GENERIC_HUBS,
    PROFANITY,
    PROPER_NOUN_ALLOWLIST,
    STOPWORDS,
)


@pytest.fixture
def chain():
    return build_chain(Config(), AllowAllPosChecker())


@pytest.mark.parametrize("word", ["apple", "gravity", "ocean", "abc"])
def test_normalised_accepts_plain_lowercase(word):
    assert is_normalised(word)


@pytest.mark.parametrize(
    "word",
    [
        "ice_cream",  # ConceptNet multiword -- must never reach a tile
        "Apple",  # uppercase: data is lowercase everywhere
        "café",  # combining accent
        "co-op",
        "don't",
        "x1",
        "",
        "two words",
    ],
)
def test_normalised_rejects_everything_else(word):
    assert not is_normalised(word)


def test_multiword_is_rejected_by_the_chain(chain):
    assert first_rejecting(chain, "ice_cream") == "not_normalised"


@pytest.mark.parametrize("word", ["ab", "a", "extraordinarily"])
def test_length_bounds(chain, word):
    assert first_rejecting(chain, word) == "bad_length"


def test_stopwords_rejected(chain):
    assert first_rejecting(chain, "the") is not None
    assert first_rejecting(chain, "because") == "stopword"


def test_generic_hubs_rejected(chain):
    assert first_rejecting(chain, "thing") == "generic_hub"
    assert first_rejecting(chain, "stuff") == "generic_hub"


def test_profanity_rejected(chain):
    sample = sorted(PROFANITY)[0]
    assert first_rejecting(chain, sample) is not None


def test_good_words_survive(chain):
    for word in ["apple", "gravity", "ocean", "newton", "tide"]:
        assert first_rejecting(chain, word) is None, word


def test_pos_filter_is_the_only_thing_rejecting_a_verb():
    """With a permissive POS checker a non-noun survives; with a strict one it
    does not. Proves the filter is actually wired in rather than decorative."""

    class NounsOnly:
        def is_noun(self, word: str) -> bool:
            return word == "apple"

    permissive = build_chain(Config(), AllowAllPosChecker())
    strict = build_chain(Config(), NounsOnly())

    assert first_rejecting(permissive, "swimming") is None
    assert first_rejecting(strict, "swimming") == "not_noun"
    assert first_rejecting(strict, "apple") is None


def test_proper_noun_allowlist_bypasses_the_pos_filter():
    """WordNet classifies many proper nouns as instances, not common nouns.
    The allowlist is what keeps `newton` -- and the best puzzles use it."""

    class RejectsEverything:
        def is_noun(self, word: str) -> bool:
            return False

    chain = build_chain(Config(), RejectsEverything())
    assert first_rejecting(chain, "newton") is None
    assert first_rejecting(chain, "rome") is None
    # Short enough to clear the length filter, so `not_noun` is genuinely the
    # rule doing the rejecting here.
    assert first_rejecting(chain, "quartz") == "not_noun"


def test_wordlists_are_disjoint_where_it_matters():
    """A word in two lists is a maintenance trap: fixing one leaves the other."""
    assert not (STOPWORDS & PROFANITY)
    assert not (GENERIC_HUBS & PROFANITY)
    assert not (PROPER_NOUN_ALLOWLIST & STOPWORDS)
    assert not (PROPER_NOUN_ALLOWLIST & GENERIC_HUBS)
    assert not (PROPER_NOUN_ALLOWLIST & PROFANITY)


def test_all_curated_words_are_themselves_normalised():
    """A list entry that can never match anything is dead weight and a lie."""
    for name, words in [
        ("STOPWORDS", STOPWORDS),
        ("GENERIC_HUBS", GENERIC_HUBS),
        ("PROFANITY", PROFANITY),
        ("PROPER_NOUN_ALLOWLIST", PROPER_NOUN_ALLOWLIST),
    ]:
        for word in words:
            assert is_normalised(word), f"{name} contains un-normalised {word!r}"
