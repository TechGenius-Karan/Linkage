"""Which answer words a hint may confirm (planning.md 2.5.3).

Domain tier: pure.

A hint tells the player that a word is among the four answers. It never says
where the word goes -- membership is orthogonal to the count-only feedback
model, which withholds *position*, so no number of hints can leak the thing
that model exists to protect.

This module answers only one question: **which** words. The client cannot
decide for itself, because `meta` is stripped at export and the browser has no
graph, so the ordering is computed here and shipped in the payload.
"""

from __future__ import annotations

from .models import Path


def obviousness(path: Path) -> tuple[float, ...]:
    """Per-slot score: the mean weight of the two edges touching that slot.

    For `start -> s0 -> s1 -> s2 -> s3 -> end` there are five edges, and slot
    `i` sits between `weights[i]` and `weights[i + 1]`. A slot whose both links
    are strong reads as a natural step and is easy to place; a slot hanging off
    one weak edge is where the player has to think.

    Edge weight is used because it is the only signal that measurably
    discriminated reviewer taste in round 1 (planning.md 7.7.2) -- the composite
    quality score separated approvals from rejections by one hundredth of a
    point, while raw edge strength separated them by 4.00 against 3.28.
    """
    w = path.weights
    return tuple((w[i] + w[i + 1]) / 2 for i in range(len(path.steps)))


def hint_words(path: Path, count: int = 2) -> tuple[str, ...]:
    """The words a hint may confirm, in the order they are offered.

    **The second- and third-most-obvious answer words, never the first.**

    Handing over the most obvious word spends the hint on nothing: it is the
    rung the player was going to get anyway, so they press the button, learn
    what they already suspected, and are no better off. The least obvious is
    just as wrong a choice -- the hardest rung usually carries the puzzle's
    "aha", and giving it away leaves the rest feeling like admin. The second
    and third rungs are where a hint changes the position someone is in.

    Ties break by word so the result is identical for every player. A hint
    randomised per session would make two scores incomparable and hand one
    player a luckier draw, which is the one property the share text cannot
    survive.
    """
    if count < 0:
        raise ValueError("count must not be negative")

    scores = obviousness(path)
    ranked = sorted(
        zip(path.steps, scores, strict=True),
        key=lambda pair: (-pair[1], pair[0]),
    )
    # Skip rank 1 -- the giveaway -- then take from rank 2 downwards. A chain
    # with fewer slots than requested yields what it has rather than repeating.
    return tuple(word for word, _ in ranked[1 : 1 + count])
