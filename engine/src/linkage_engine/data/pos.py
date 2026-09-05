"""Part-of-speech checking via WordNet (planning.md 7.1).

Data tier: implements the `domain.ports.PosChecker` protocol declared by the
domain tier. Two implementations, which is what earns the abstraction:
the real one, and a no-op for tests and for machines without the corpus.
"""

from __future__ import annotations

CORPUS_HINT = (
    "WordNet corpus not found. Install it with:\n"
    "    python -m nltk.downloader wordnet omw-1.4\n"
    "Or pass --no-pos-filter to build a graph without the noun restriction "
    "(chains will be noticeably less coherent)."
)


class AllowAllPosChecker:
    """Accepts every word. Used by tests and by `--no-pos-filter`."""

    def is_noun(self, word: str) -> bool:  # noqa: ARG002 - protocol shape
        return True


class WordNetPosChecker:
    """True when WordNet knows at least one noun sense for the word.

    Results are cached: the vocabulary chain queries at most `vocab_fetch_n`
    distinct words, but Phase 2 will re-query the same words repeatedly.
    """

    def __init__(self) -> None:
        try:
            from nltk.corpus import wordnet
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise RuntimeError("nltk is not installed") from exc

        try:
            # Force corpus load now, so a missing corpus fails at construction
            # with an actionable message rather than midway through a build.
            wordnet.synsets("test", pos=wordnet.NOUN)
        except LookupError as exc:
            raise RuntimeError(CORPUS_HINT) from exc

        self._wordnet = wordnet
        # Plain dict rather than lru_cache-on-a-method: that variant keys the
        # cache on `self` and keeps instances alive, which is a leak waiting
        # for a second instance to exist.
        self._cache: dict[str, bool] = {}

    def is_noun(self, word: str) -> bool:
        hit = self._cache.get(word)
        if hit is None:
            hit = bool(self._wordnet.synsets(word, pos=self._wordnet.NOUN))
            self._cache[word] = hit
        return hit


def make_pos_checker(enabled: bool):
    """Pick an implementation. The only place the choice is made."""
    return WordNetPosChecker() if enabled else AllowAllPosChecker()
