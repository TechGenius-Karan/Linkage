"""What a reviewer has decided about a candidate (planning.md 16.2).

Domain tier: pure. No I/O, no filesystem, no clock beyond what is handed in.

The state machine is small on purpose:

    candidate --approve--> approved (undated) --schedule--> scheduled
        |                       ^     |                        |
        +-- reject -------------+     +-- unapprove            +-- unschedule
            (reason, badLink)

**Approving records taste; it schedules nothing.** An approved decision carries
`date=None` until somebody separately chooses one. Round 1's reviewer was
explicit that an approval must not imply a shipping date, and 7.7.3 records the
coupling as an open defect -- this module is where it stops existing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal, Sequence

#: "accept" rather than "approve" because that is the token `review.py` has
#: always written; the admin UI says "Approve" on the button either way. A
#: label and a stored token do not have to be the same word.
Verdict = Literal["accept", "reject"]
ACCEPT: Verdict = "accept"
REJECT: Verdict = "reject"

#: A chain has `CHAIN_LINKS` edges: start->s0, s0->s1, s1->s2, s2->s3, s3->end.
#: `bad_link` indexes those, so 0 is the opening move and 4 is the closing one.
CHAIN_LINKS = 5


class DecisionError(ValueError):
    """A transition the state machine refuses. Carries a reason for the UI."""


@dataclass(frozen=True, slots=True)
class BankEdit:
    """One word swapped for another during review (planning.md 16.4)."""

    removed: str
    added: str


@dataclass(frozen=True, slots=True)
class Decision:
    """One reviewer judgement, keyed elsewhere by the candidate's content hash."""

    verdict: Verdict
    decided_at: str  # ISO date; passed in, never read from a clock here
    reason: str | None = None
    #: Which rung failed, 0..4. The single most useful thing a reviewer can
    #: report (planning.md 7.7.3): free text cannot be aggregated across a
    #: hundred verdicts, a rung index can.
    bad_link: int | None = None
    bank_edits: tuple[BankEdit, ...] = ()
    #: None until scheduled. Approving does not set this.
    date: str | None = None

    def __post_init__(self) -> None:
        if self.verdict not in (ACCEPT, REJECT):
            raise DecisionError(f"unknown verdict {self.verdict!r}")
        if self.bad_link is not None and not 0 <= self.bad_link < CHAIN_LINKS:
            raise DecisionError(f"bad_link must be 0..{CHAIN_LINKS - 1}, got {self.bad_link}")
        if self.verdict == "reject" and self.date is not None:
            raise DecisionError("a rejected puzzle cannot hold a date")

    @property
    def is_scheduled(self) -> bool:
        return self.verdict == ACCEPT and self.date is not None

    @property
    def is_pooled(self) -> bool:
        """Approved and waiting for a date -- the state 16.2 exists to create."""
        return self.verdict == ACCEPT and self.date is None


# --------------------------------------------------------------------------
# Transitions
# --------------------------------------------------------------------------


def approve(decided_at: str, *, edits: tuple[BankEdit, ...] = ()) -> Decision:
    return Decision(verdict=ACCEPT, decided_at=decided_at, bank_edits=edits)


def reject(decided_at: str, *, reason: str, bad_link: int | None = None) -> Decision:
    """Reject, with a reason that is not optional.

    A rejection with no reason teaches the next generation nothing, and the
    whole point of storing verdicts is that they eventually rebuild the quality
    scorer (planning.md 7.7.3).
    """
    if not reason.strip():
        raise DecisionError("a rejection needs a reason")
    return Decision(
        verdict=REJECT,
        decided_at=decided_at,
        reason=reason.strip(),
        bad_link=bad_link,
    )


def schedule(decision: Decision, date: str) -> Decision:
    """Put an approved, undated decision on a date."""
    if decision.verdict != ACCEPT:
        raise DecisionError("only an approved puzzle can be scheduled")
    if decision.date is not None:
        raise DecisionError(f"already scheduled for {decision.date}")
    return replace(decision, date=date)


def unschedule(decision: Decision) -> Decision:
    """Pull a puzzle off its date, back into the undated pool.

    Deliberately *not* the same as unapproving: the reviewer still likes it.
    """
    if not decision.is_scheduled:
        raise DecisionError("that puzzle is not scheduled")
    return replace(decision, date=None)


def unapprove(decision: Decision) -> Decision:
    """Return an approved puzzle to the queue, undecided.

    Refuses while it is still scheduled, rather than silently dropping the date
    -- a puzzle vanishing from the calendar as a side effect of a different
    button is exactly the class of bug that loses work.
    """
    if decision.verdict != ACCEPT:
        raise DecisionError("that puzzle is not approved")
    if decision.date is not None:
        raise DecisionError("unschedule it first -- it is on the calendar")
    return decision  # caller removes the entry; returned for a uniform signature


def apply_edits(bank: Sequence[str], edits: Sequence[BankEdit]) -> tuple[str, ...]:
    """Replay recorded swaps over a candidate's original bank (planning.md 16.4).

    The edits live on the **decision**, never on the candidate, because
    `Candidate.content_hash()` covers the bank as a set: rewriting the bank in
    `candidates.json` would change the hash and orphan the very judgement the
    swap was part of. So the generated puzzle stays exactly as generated, the
    edit list is replayed on read, and the change stays auditable.

    Sorted on the way out, like every other bank in this engine -- a bank whose
    order depended on edit history would make the export non-deterministic.
    """
    current = list(bank)
    for edit in edits:
        if edit.removed not in current:
            raise DecisionError(
                f"cannot replay swap: {edit.removed!r} is not in the bank"
            )
        current[current.index(edit.removed)] = edit.added
    if len(set(current)) != len(current):
        raise DecisionError("replaying the swaps produced a duplicate bank word")
    return tuple(sorted(current))


def record_swap(decision: Decision, removed: str, added: str) -> Decision:
    """Note a bank word swapped during review (planning.md 16.4).

    The uniqueness re-check lives in the data tier, where the graph is. By the
    time a swap reaches here it has already been proved safe.
    """
    if removed == added:
        raise DecisionError("that swap changes nothing")
    return replace(decision, bank_edits=(*decision.bank_edits, BankEdit(removed, added)))


# --------------------------------------------------------------------------
# Serialisation
# --------------------------------------------------------------------------


def to_json(decision: Decision) -> dict:
    return {
        "verdict": decision.verdict,
        "decidedAt": decision.decided_at,
        "reason": decision.reason,
        "badLink": decision.bad_link,
        "bankEdits": [{"removed": e.removed, "added": e.added} for e in decision.bank_edits],
        "date": decision.date,
    }


def _verdict(value: object) -> Verdict:
    """`approve` is accepted as a spelling of `accept`.

    Hand-written review files use it, and refusing to load a file over one
    synonym would be the tool losing a reviewer's work on a technicality.
    """
    if value in (ACCEPT, REJECT):
        return value  # type: ignore[return-value]
    if value == "approve":
        return ACCEPT
    raise DecisionError(f"unknown verdict {value!r}")


def from_json(raw: object) -> Decision:
    """Parse one stored decision.

    Tolerates the original flat shape -- `decisions.json` used to map a hash
    straight to a verdict string, and a file written by the terminal TUI must
    still load rather than crashing the tool that replaced it.
    """
    if isinstance(raw, str):
        return Decision(verdict=_verdict(raw), decided_at="")
    if not isinstance(raw, dict):
        raise DecisionError(f"cannot read decision from {type(raw).__name__}")

    edits = tuple(
        BankEdit(removed=str(e["removed"]), added=str(e["added"]))
        for e in raw.get("bankEdits", ())
        if isinstance(e, dict) and "removed" in e and "added" in e
    )
    return Decision(
        verdict=_verdict(raw.get("verdict", REJECT)),
        decided_at=str(raw.get("decidedAt", "")),
        reason=raw.get("reason"),
        bad_link=raw.get("badLink"),
        bank_edits=edits,
        date=raw.get("date"),
    )


# --------------------------------------------------------------------------
# Views over the whole set
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Split:
    """Every hash, grouped by where it sits in the machine."""

    approved_pool: tuple[str, ...] = field(default=())
    scheduled: tuple[str, ...] = field(default=())
    rejected: tuple[str, ...] = field(default=())


def split(decisions: dict[str, Decision]) -> Split:
    """Sorted for reproducibility -- an admin queue that reorders itself between
    reloads is one a reviewer loses their place in."""
    return Split(
        approved_pool=tuple(sorted(h for h, d in decisions.items() if d.is_pooled)),
        scheduled=tuple(
            sorted(
                (h for h, d in decisions.items() if d.is_scheduled),
                key=lambda h: (decisions[h].date or "", h),
            )
        ),
        rejected=tuple(sorted(h for h, d in decisions.items() if d.verdict == REJECT)),
    )


def taken_dates(decisions: dict[str, Decision]) -> dict[str, str]:
    """date -> hash, for every scheduled puzzle. Two puzzles on one day is the
    error most worth catching before it reaches export."""
    taken: dict[str, str] = {}
    for hash_, decision in sorted(decisions.items()):
        if decision.date is not None:
            if decision.date in taken:
                raise DecisionError(f"{decision.date} already holds {taken[decision.date]}")
            taken[decision.date] = hash_
    return taken
