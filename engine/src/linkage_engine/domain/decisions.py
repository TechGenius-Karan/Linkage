"""What a reviewer has decided about a candidate (planning.md 16.2).

Domain tier: pure. No I/O, no filesystem, no clock beyond what is handed in.

The state machine is small on purpose:

    candidate --approve--> approved (undated) --schedule--> scheduled
        |                    ^  ^     |                        |
        +-- reject ----------+  |     +-- unapprove            +-- unschedule
            (reason, badLink)   |
                                +-- revisit (back for another look)

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
Verdict = Literal["accept", "reject", "revisit"]
ACCEPT: Verdict = "accept"
REJECT: Verdict = "reject"
#: Approved once, then pulled back for another look (docs/admin.md 12.1). Not a
#: flag on `accept`: it is neither approved nor undecided, and a flag would let
#: it leak into the pool through any query that forgot to check it.
REVISIT: Verdict = "revisit"

#: A chain has `CHAIN_LINKS` edges: start->s0, s0->s1, s1->s2, s2->s3, s3->end.
#: `bad_link` indexes those, so 0 is the opening move and 4 is the closing one.
CHAIN_LINKS = 5


class DecisionError(ValueError):
    """A transition the state machine refuses. Carries a reason for the UI."""


#: Which part of a puzzle a hand edit touches (docs/admin.md 11.1).
EditField = Literal["start", "end", "solution", "bank"]
EDIT_FIELDS: tuple[EditField, ...] = ("start", "end", "solution", "bank")


@dataclass(frozen=True, slots=True)
class WordEdit:
    """One word replaced by hand.

    Generalises the original `BankEdit`, which could only touch decoys. The
    reviewer may now rewrite any word in the puzzle -- answers and endpoints
    included -- because their judgement is the authority on whether a chain
    reads (docs/admin.md 11).

    `index` positions the edit inside the solution, where order is meaning.
    The bank is a set and matches by word, so `index` is None there and for
    the endpoints.
    """

    field: EditField
    removed: str
    added: str
    index: int | None = None

    def __post_init__(self) -> None:
        if self.field not in EDIT_FIELDS:
            raise DecisionError(f"unknown edit field {self.field!r}")
        if self.field == "solution" and self.index is None:
            raise DecisionError("a solution edit needs the rung it replaces")
        if self.field != "solution" and self.index is not None:
            raise DecisionError(f"a {self.field} edit takes no index")
        if not self.added:
            raise DecisionError("an edit needs a replacement word")


#: A link the reviewer asserted that ConceptNet does not carry
#: (docs/admin.md 11.2). Exported with the puzzle, so CI re-proves it against
#: the same evidence the reviewer saw.
ManualEdge = tuple[str, str, float]


@dataclass(frozen=True, slots=True)
class Puzzle:
    """A puzzle as it currently stands, after any hand edits are replayed."""

    start: str
    end: str
    solution: tuple[str, ...]
    bank: tuple[str, ...]

    @property
    def nodes(self) -> tuple[str, ...]:
        return (self.start, *self.solution, self.end)


def BankEdit(removed: str, added: str) -> WordEdit:  # noqa: N802
    """A decoy swap -- the original, and still the common, kind of edit.

    Kept as a constructor rather than deleted: `swap_decoy` and every existing
    test say `BankEdit(a, b)`, and there is no reason to churn them for a
    field that is always "bank".
    """
    return WordEdit(field="bank", removed=removed, added=added)


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
    bank_edits: tuple[WordEdit, ...] = ()
    #: Links the reviewer asserted that ConceptNet does not carry
    #: (docs/admin.md 11.2). Exported with the puzzle so the golden test
    #: re-proves it against the evidence the reviewer actually saw.
    manual_edges: tuple[ManualEdge, ...] = ()
    #: None until scheduled. Approving does not set this.
    date: str | None = None

    def __post_init__(self) -> None:
        if self.verdict not in (ACCEPT, REJECT, REVISIT):
            raise DecisionError(f"unknown verdict {self.verdict!r}")
        if self.bad_link is not None and not 0 <= self.bad_link < CHAIN_LINKS:
            raise DecisionError(f"bad_link must be 0..{CHAIN_LINKS - 1}, got {self.bad_link}")
        if self.verdict != ACCEPT and self.date is not None:
            raise DecisionError(f"a {self.verdict}ed puzzle cannot hold a date")

    @property
    def is_scheduled(self) -> bool:
        return self.verdict == ACCEPT and self.date is not None

    @property
    def is_returned(self) -> bool:
        """Sent back to review. Excluded from the pool and from export."""
        return self.verdict == REVISIT

    @property
    def is_pooled(self) -> bool:
        """Approved and waiting for a date -- the state 16.2 exists to create."""
        return self.verdict == ACCEPT and self.date is None


# --------------------------------------------------------------------------
# Transitions
# --------------------------------------------------------------------------


def approve(
    decided_at: str,
    *,
    edits: tuple[WordEdit, ...] = (),
    manual_edges: tuple[ManualEdge, ...] = (),
) -> Decision:
    """Record that the reviewer wants this puzzle, with whatever they changed.

    `manual_edges` are links they asserted that ConceptNet does not carry
    (docs/admin.md 11.2). They ship with the puzzle, because the golden test
    re-proves it in CI and has to see the same evidence the reviewer did.
    """
    return Decision(
        verdict=ACCEPT,
        decided_at=decided_at,
        bank_edits=edits,
        manual_edges=manual_edges,
    )


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


def revisit(decided_at: str, decision: Decision) -> Decision:
    """Pull an approved puzzle back for another look (docs/admin.md 12.1).

    Records **no reason**. `reject` demands one because rejections are the data
    that will eventually rebuild the scorer; "I want another look" is a state
    change and teaches the generator nothing, and a second place to type would
    only dilute the one that matters.

    Refuses while scheduled for the same reason `unapprove` does: a puzzle
    leaving the calendar as a side effect of a different button is the class of
    bug that loses work.
    """
    if decision.verdict != ACCEPT:
        raise DecisionError("only an approved puzzle can be sent back")
    if decision.date is not None:
        raise DecisionError("unschedule it first -- it is on the calendar")
    # Edits survive: the reviewer wanted another look at the puzzle they made,
    # not at the one the generator made.
    return Decision(
        verdict=REVISIT,
        decided_at=decided_at,
        bank_edits=decision.bank_edits,
        manual_edges=decision.manual_edges,
    )


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


def apply_edits(bank: Sequence[str], edits: Sequence[WordEdit]) -> tuple[str, ...]:
    """Replay bank swaps over a candidate's original bank (docs/admin.md 5.1).

    Narrow form, kept because most callers only ever touch decoys. Edits for
    other fields are ignored here; `apply_puzzle_edits` replays all of them.

    Sorted on the way out, like every other bank in this engine -- a bank whose
    order depended on edit history would make the export non-deterministic.
    """
    current = list(bank)
    for edit in edits:
        if edit.field != "bank":
            continue
        if edit.removed not in current:
            raise DecisionError(
                f"cannot replay swap: {edit.removed!r} is not in the bank"
            )
        current[current.index(edit.removed)] = edit.added
    if len(set(current)) != len(current):
        raise DecisionError("replaying the swaps produced a duplicate bank word")
    return tuple(sorted(current))


def apply_puzzle_edits(
    start: str,
    end: str,
    solution: Sequence[str],
    bank: Sequence[str],
    edits: Sequence[WordEdit],
) -> Puzzle:
    """Replay every hand edit over a whole puzzle (docs/admin.md 11.1).

    The edits live on the **decision**, never on the candidate, because
    `Candidate.content_hash()` covers the endpoints, the ordered solution and
    the bank: rewriting any of them in `candidates.json` would change the hash
    and orphan the very judgement the edit was part of. So the generated puzzle
    stays exactly as generated, the edit list is replayed on read, and the
    change stays auditable.

    **A solution or endpoint edit carries into the bank.** The bank contains
    the solution by definition, so renaming a rung and leaving the old word
    sitting among the decoys would ship a puzzle whose answer is beside its own
    red herring. Nothing else would catch it: the uniqueness proof would pass,
    because a stale answer word is just another decoy that happens not to fit.
    """
    current_solution = list(solution)
    current_bank = list(bank)
    current_start, current_end = start, end

    for edit in edits:
        if edit.field == "bank":
            if edit.removed not in current_bank:
                raise DecisionError(
                    f"cannot replay edit: {edit.removed!r} is not in the bank"
                )
            current_bank[current_bank.index(edit.removed)] = edit.added
        elif edit.field == "solution":
            index = edit.index or 0
            if not 0 <= index < len(current_solution):
                raise DecisionError(f"no rung {index} to replay an edit onto")
            was = current_solution[index]
            current_solution[index] = edit.added
            # The bank holds the solution; move the word there too, or the old
            # answer stays on the board as a decoy.
            if was in current_bank:
                current_bank[current_bank.index(was)] = edit.added
            elif edit.added not in current_bank:
                current_bank.append(edit.added)
        elif edit.field == "start":
            current_start = edit.added
        else:
            current_end = edit.added

    if len(set(current_bank)) != len(current_bank):
        raise DecisionError("replaying the edits produced a duplicate bank word")
    if len(set(current_solution)) != len(current_solution):
        raise DecisionError("replaying the edits produced a duplicate answer word")
    return Puzzle(
        start=current_start,
        end=current_end,
        solution=tuple(current_solution),
        bank=tuple(sorted(current_bank)),
    )


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
        "bankEdits": [
            {
                "field": e.field,
                "removed": e.removed,
                "added": e.added,
                **({"index": e.index} if e.index is not None else {}),
            }
            for e in decision.bank_edits
        ],
        "manualEdges": [list(edge) for edge in decision.manual_edges],
        "date": decision.date,
    }


def _verdict(value: object) -> Verdict:
    """`approve` is accepted as a spelling of `accept`.

    Hand-written review files use it, and refusing to load a file over one
    synonym would be the tool losing a reviewer's work on a technicality.
    """
    if value in (ACCEPT, REJECT, REVISIT):
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

    # `field` is absent in anything written before hand editing existed, and
    # everything written then was a decoy swap.
    edits = tuple(
        WordEdit(
            field=e.get("field", "bank"),
            removed=str(e["removed"]),
            added=str(e["added"]),
            index=e.get("index"),
        )
        for e in raw.get("bankEdits", ())
        if isinstance(e, dict) and "removed" in e and "added" in e
    )
    manual = tuple(
        (str(edge[0]), str(edge[1]), float(edge[2]))
        for edge in raw.get("manualEdges", ())
        if isinstance(edge, (list, tuple)) and len(edge) == 3
    )
    return Decision(
        verdict=_verdict(raw.get("verdict", REJECT)),
        decided_at=str(raw.get("decidedAt", "")),
        reason=raw.get("reason"),
        bad_link=raw.get("badLink"),
        bank_edits=edits,
        manual_edges=manual,
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
    returned: tuple[str, ...] = field(default=())


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
        returned=tuple(sorted(h for h, d in decisions.items() if d.is_returned)),
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
