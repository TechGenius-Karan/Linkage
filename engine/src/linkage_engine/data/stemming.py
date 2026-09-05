"""Stemming (planning.md 7.6).

Data tier: implements `domain.ports.Stemmer`. NLTK's Porter stemmer is pure
Python with no corpus download, so unlike WordNet this one always works.
"""

from __future__ import annotations


class IdentityStemmer:
    """Returns the word unchanged. Only exact duplicates collide.

    Used in tests that are not about stemming, so a stemmer quirk can never
    be the reason an unrelated assertion fails.
    """

    def stem(self, word: str) -> str:
        return word


class PorterStemmerAdapter:
    """NLTK's Porter stemmer behind the domain's `Stemmer` protocol.

    The adapter exists so `domain/` never imports nltk -- the layering test
    enforces that, and it keeps the domain testable with no dependencies.
    """

    def __init__(self) -> None:
        from nltk.stem import PorterStemmer

        self._stemmer = PorterStemmer()
        self._cache: dict[str, str] = {}

    def stem(self, word: str) -> str:
        hit = self._cache.get(word)
        if hit is None:
            hit = self._stemmer.stem(word)
            self._cache[word] = hit
        return hit
