"""Build the puzzle vocabulary from word-frequency data (planning.md 7.1).

Data tier: reaches out to `wordfreq`'s bundled dataset. The rules about what
makes a good puzzle word live in `domain.filters`; this module only supplies
candidates and tallies the outcome.
"""

from __future__ import annotations

from wordfreq import top_n_list

from ..config import Config
from ..domain.filters import build_chain, first_rejecting
from ..domain.models import VocabularyResult
from ..domain.ports import PosChecker


def build_vocabulary(cfg: Config, pos: PosChecker) -> VocabularyResult:
    """Frequency-ranked candidates, filtered down to `cfg.vocab_target`.

    `vocab_min_rank` skips the head of the list: the 500 most frequent English
    words are too generic to surprise anyone, so they make poor puzzle words
    even when they survive every other filter.

    The rejection breakdown is returned, not logged and discarded -- it is the
    only way to see which filter is actually doing the work when a build comes
    out the wrong size.
    """
    chain = build_chain(cfg, pos)
    candidates = top_n_list("en", cfg.vocab_fetch_n)[cfg.vocab_min_rank :]

    words: list[str] = []
    rejected: dict[str, int] = {f.name: 0 for f in chain}

    for word in candidates:
        if len(words) >= cfg.vocab_target:
            break
        reason = first_rejecting(chain, word)
        if reason is None:
            words.append(word)
        else:
            rejected[reason] += 1

    return VocabularyResult(
        words=frozenset(words),
        considered=len(candidates),
        rejected_by=rejected,
    )
