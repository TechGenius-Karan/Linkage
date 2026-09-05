"""Interfaces the domain tier needs, declared by the domain tier.

Dependency Inversion in its load-bearing form (planning.md 4.2, 5): the logic
tier owns the contract and the data tier conforms to it. Nothing here imports
nltk, requests, or the filesystem.
"""

from __future__ import annotations

from typing import Protocol


class PosChecker(Protocol):
    """Decides whether a word can serve as a noun.

    Two real implementations justify this abstraction:
      - `data.pos.WordNetPosChecker`  -- real lookups via NLTK/WordNet
      - `data.pos.AllowAllPosChecker` -- no-op, for tests and for building a
        graph on a machine without the WordNet corpus installed
    """

    def is_noun(self, word: str) -> bool:
        """True when `word` has at least one noun sense."""
        ...


class Stemmer(Protocol):
    """Reduces a word to its stem, so `moon` and `moons` collide.

    Used to keep morphological near-duplicates out of the same word bank
    (planning.md 7.6). Two implementations:
      - `data.stemming.PorterStemmerAdapter` -- real, via NLTK
      - `data.stemming.IdentityStemmer`      -- tests, and a graph build on a
        machine without NLTK's data
    """

    def stem(self, word: str) -> str:
        """Canonical stem. Equal stems mean the words are morphological kin."""
        ...
