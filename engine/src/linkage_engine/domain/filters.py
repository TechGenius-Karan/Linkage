"""The vocabulary filter chain (planning.md 7.1, 3.1.1).

Domain tier: pure predicates over a single word.

Open/Closed: the chain is a list of named filters. Adding a rule means
appending one entry -- `build_vocabulary` is never edited. Names are not
cosmetic either: they drive the rejection breakdown that tells us which filter
is actually doing the work, which is the only way to tune this sensibly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from ..config import Config
from .ports import PosChecker
from .wordlists import GENERIC_HUBS, PROFANITY, PROPER_NOUN_ALLOWLIST, STOPWORDS

#: Canonical word form (planning.md 3.1.1): lowercase ASCII letters only.
#: Rejects digits, hyphens, apostrophes, accents, and -- importantly --
#: ConceptNet's multiword lemmas such as `ice_cream`.
NORMALISED = re.compile(r"^[a-z]+$")


@dataclass(frozen=True, slots=True)
class WordFilter:
    """A named predicate. `keep(word)` is True when the word survives."""

    name: str
    keep: Callable[[str], bool]


def is_normalised(word: str) -> bool:
    """Lowercase ASCII letters only -- no digits, punctuation, or underscores."""
    return bool(NORMALISED.fullmatch(word))


def build_chain(cfg: Config, pos: PosChecker) -> tuple[WordFilter, ...]:
    """Assemble the filter chain in evaluation order.

    Ordered cheapest-first so the expensive WordNet lookup only ever runs on
    words that already passed every string test.
    """
    return (
        WordFilter("not_normalised", is_normalised),
        WordFilter(
            "bad_length",
            lambda w: cfg.word_min_len <= len(w) <= cfg.word_max_len,
        ),
        WordFilter("stopword", lambda w: w not in STOPWORDS),
        WordFilter("profanity", lambda w: w not in PROFANITY),
        WordFilter("generic_hub", lambda w: w not in GENERIC_HUBS),
        # Mixed part-of-speech chains (apple -> red -> running -> fast) read as
        # incoherent; noun-dominant chains read as thought. The allowlist
        # bypass keeps high-recognition proper nouns that WordNet would
        # otherwise classify as instances rather than common nouns.
        WordFilter(
            "not_noun",
            lambda w: w in PROPER_NOUN_ALLOWLIST or pos.is_noun(w),
        ),
    )


def first_rejecting(chain: tuple[WordFilter, ...], word: str) -> str | None:
    """Name of the first filter that rejects `word`, or None if it survives."""
    for f in chain:
        if not f.keep(word):
            return f.name
    return None
