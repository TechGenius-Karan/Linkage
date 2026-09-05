"""Vocabulary construction (planning.md 7.1).

Uses `AllowAllPosChecker` so the suite never needs the WordNet corpus --
the POS filter itself is covered in `test_filters.py`.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from linkage_engine.config import Config
from linkage_engine.data.pos import AllowAllPosChecker
from linkage_engine.data.vocabulary import build_vocabulary
from linkage_engine.domain.filters import is_normalised
from linkage_engine.domain.wordlists import GENERIC_HUBS, PROFANITY, STOPWORDS

# Small enough to stay fast, large enough to exercise every filter.
SMALL = Config(vocab_fetch_n=3000, vocab_target=250, vocab_min_rank=100)


@pytest.fixture(scope="module")
def result():
    return build_vocabulary(SMALL, AllowAllPosChecker())


def test_never_exceeds_the_target(result):
    assert result.kept <= SMALL.vocab_target


def test_produces_a_useful_number_of_words(result):
    """A near-empty vocabulary means the filters are misconfigured."""
    assert result.kept > 100


def test_every_surviving_word_is_normalised(result):
    for word in result.words:
        assert is_normalised(word), word
        assert SMALL.word_min_len <= len(word) <= SMALL.word_max_len


def test_no_stopwords_profanity_or_generic_hubs_survive(result):
    assert not (result.words & STOPWORDS)
    assert not (result.words & PROFANITY)
    assert not (result.words & GENERIC_HUBS)


def test_min_rank_skips_the_head_of_the_frequency_list():
    """The most frequent words are too generic to surprise anyone."""
    from wordfreq import top_n_list

    head = set(top_n_list("en", 100))
    assert not (build_vocabulary(SMALL, AllowAllPosChecker()).words & head)


def test_rejection_breakdown_is_reported_per_filter(result):
    assert result.rejected_by, "the breakdown is the only tuning feedback we get"
    assert set(result.rejected_by) == {
        "not_normalised",
        "bad_length",
        "stopword",
        "profanity",
        "generic_hub",
        "not_noun",
    }
    assert all(count >= 0 for count in result.rejected_by.values())


def test_considered_count_reflects_the_post_min_rank_pool(result):
    assert result.considered == SMALL.vocab_fetch_n - SMALL.vocab_min_rank


def test_is_deterministic():
    """Same config, same wordfreq version, same words -- every time
    (planning.md 7.8)."""
    a = build_vocabulary(SMALL, AllowAllPosChecker())
    b = build_vocabulary(SMALL, AllowAllPosChecker())
    assert a.words == b.words
    assert a.rejected_by == b.rejected_by


def test_a_tighter_length_bound_shrinks_the_vocabulary():
    narrow = build_vocabulary(replace(SMALL, word_max_len=4), AllowAllPosChecker())
    assert all(len(w) <= 4 for w in narrow.words)
