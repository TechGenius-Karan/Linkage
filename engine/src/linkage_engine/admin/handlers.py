"""Admin request handlers (planning.md 16.3).

Presentation tier: parse a request, call the domain, return JSON. No HTTP types
appear here -- `server.py` owns those -- so every handler is a plain function
call in a test.
"""

from __future__ import annotations

from datetime import date, timedelta

import networkx as nx

from ..config import Config
from ..data import exporters
from ..data.stemming import PorterStemmerAdapter
from ..domain import corpus
from ..domain import decisions as dec
from ..domain import distractors
from ..domain.models import Path as ChainPath


class BadRequest(ValueError):
    """The reviewer asked for something impossible. Becomes a 400 with the text."""


def _today() -> str:
    return date.today().isoformat()


def _candidate_view(row: dict, decision: dec.Decision | None = None) -> dict:
    """One candidate, shaped for the queue.

    `chain` is the whole ladder including the endpoints, and `linkWeights` runs
    parallel to it -- so the UI can put a weight *between* two words without
    recomputing anything. That pairing is what makes marking a bad link
    (planning.md 16.2) a click rather than a guess.

    `bank` is the **effective** bank: the generated one with any recorded swaps
    replayed over it (planning.md 16.4). `candidates.json` is never rewritten,
    because the content hash covers the bank and editing it in place would
    orphan the decision that holds the edit.
    """
    solution = list(row["solution"])
    chain = [row["start"], *solution, row["end"]]
    edits = decision.bank_edits if decision is not None else ()
    try:
        bank = list(dec.apply_edits(row["bank"], edits))
    except dec.DecisionError as exc:
        raise BadRequest(str(exc)) from exc
    return {
        "hash": row["hash"],
        "start": row["start"],
        "end": row["end"],
        "solution": solution,
        "chain": chain,
        "decoys": [w for w in bank if w not in set(solution)],
        "bank": bank,
        "quality": row.get("quality"),
        "linkWeights": list(row.get("weights", ())),
        "relations": [list(r) for r in row.get("relations", ())],
        "bankEdits": [{"removed": e.removed, "added": e.added} for e in edits],
        "date": decision.date if decision is not None else None,
    }


def _path_from_row(row: dict) -> ChainPath:
    """Rehydrate the chain, for the graph work that a swap needs."""
    return ChainPath(
        start=row["start"],
        end=row["end"],
        steps=tuple(row["solution"]),
        weights=tuple(row["weights"]),
        relations=tuple(tuple(r) for r in row["relations"]),
    )


def read_edits(raw: object) -> tuple[dec.BankEdit, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise BadRequest("edits must be a list")
    out: list[dec.BankEdit] = []
    for entry in raw:
        if not isinstance(entry, dict) or not entry.get("removed") or not entry.get("added"):
            raise BadRequest("each edit needs a removed and an added word")
        out.append(dec.BankEdit(removed=str(entry["removed"]), added=str(entry["added"])))
    return tuple(out)


def queue(cfg: Config, *, limit: int | None = None) -> dict:
    """Candidates with no verdict yet, hardest-first by quality.

    The ordering is the scorer's, and 7.7.2 is candid that it barely beats
    chance -- but a queue ordered badly is still a queue, and stable ordering
    matters more here than good ordering: a reviewer who reloads must not lose
    their place.
    """
    rows = exporters.read_candidates(cfg.candidates_path)
    decisions = exporters.read_decisions(cfg.decisions_path)

    pending = [r for r in rows if r["hash"] not in decisions]
    pending.sort(key=lambda r: (-(r.get("quality") or 0.0), r["hash"]))

    split = dec.split(decisions)
    return {
        "puzzles": [_candidate_view(r) for r in pending[:limit]],
        "counts": {
            "total": len(rows),
            "pending": len(pending),
            "approved": len(split.approved_pool) + len(split.scheduled),
            "scheduled": len(split.scheduled),
            "rejected": len(split.rejected),
        },
    }


def _load_pair(cfg: Config, hash_: str) -> tuple[dict, dict[str, dec.Decision]]:
    rows = {r["hash"]: r for r in exporters.read_candidates(cfg.candidates_path)}
    if hash_ not in rows:
        raise BadRequest(f"no candidate with hash {hash_}")
    return rows, exporters.read_decisions(cfg.decisions_path)


def approve(
    cfg: Config,
    hash_: str,
    *,
    edits: tuple[dec.BankEdit, ...] = (),
    graph: nx.Graph | None = None,
) -> dict:
    """Record that the reviewer wants this puzzle, with any hand edits.

    The edits ride along with the approval rather than being a write of their
    own, so there is no fourth state for "edited but undecided" -- a swap is a
    preview until the reviewer commits to the puzzle it produced.

    They are re-proved here even though `swap` already proved them. The check
    is 60ms and this is the one property the whole game rests on; a client that
    skipped the preview must not be able to talk its way past it.
    """
    rows, decisions = _load_pair(cfg, hash_)
    if hash_ in decisions:
        raise BadRequest("that puzzle already has a verdict")
    if edits and graph is not None:
        _replay(cfg, graph, rows[hash_], edits)

    decisions[hash_] = dec.approve(_today(), edits=edits)
    exporters.write_decisions(cfg.decisions_path, decisions)
    # Approving records taste and schedules nothing (planning.md 16.2). The
    # response says so explicitly so the UI cannot imply otherwise.
    return {"hash": hash_, "verdict": dec.ACCEPT, "date": None}


def reject(cfg: Config, hash_: str, reason: str, bad_link: int | None = None) -> dict:
    _, decisions = _load_pair(cfg, hash_)
    if hash_ in decisions:
        raise BadRequest("that puzzle already has a verdict")

    try:
        decisions[hash_] = dec.reject(_today(), reason=reason, bad_link=bad_link)
    except dec.DecisionError as exc:
        raise BadRequest(str(exc)) from exc

    exporters.write_decisions(cfg.decisions_path, decisions)
    return {"hash": hash_, "verdict": dec.REJECT, "badLink": bad_link}


def undo(cfg: Config, hash_: str) -> dict:
    """Drop a verdict and return the puzzle to the queue.

    Not in the original plan, and added because the reviewer is one keystroke
    from a wrong verdict with no way back. A review tool without an undo makes
    people hesitate over every click, which costs more than the feature.
    """
    _, decisions = _load_pair(cfg, hash_)
    decision = decisions.get(hash_)
    if decision is None:
        raise BadRequest("that puzzle has no verdict to undo")
    if decision.date is not None:
        raise BadRequest("unschedule it first -- it is on the calendar")

    del decisions[hash_]
    exporters.write_decisions(cfg.decisions_path, decisions)
    return {"hash": hash_, "verdict": None}


# --------------------------------------------------------------------------
# 6b -- refining a bank, with the engine holding a veto (planning.md 16.4)
# --------------------------------------------------------------------------

#: One instance, because the Porter stemmer memoises and a swap asks it about
#: the same eleven words over and over.
_STEMMER = PorterStemmerAdapter()


def _replay(
    cfg: Config, graph: nx.Graph, row: dict, edits: tuple[dec.BankEdit, ...]
) -> tuple[str, ...]:
    """Apply every edit in order, proving the bank after each one.

    Proving each step rather than only the final bank is what makes the
    *reason* accurate: the reviewer is told which swap was refused, rather
    than that something, somewhere, was.
    """
    path = _path_from_row(row)
    bank = tuple(row["bank"])
    for edit in edits:
        try:
            bank = distractors.swap_decoy(
                cfg, graph, _STEMMER, path, bank, edit.removed, edit.added
            )
        except distractors.SwapRefused as exc:
            raise BadRequest(str(exc)) from exc
    return bank


def swap(
    cfg: Config, graph: nx.Graph, hash_: str, edits: tuple[dec.BankEdit, ...]
) -> dict:
    """Preview a bank edit. Proves it, and **writes nothing**.

    Refusing is the whole point (planning.md 16.4): the reviewer cannot break
    uniqueness by hand even deliberately, and a refused swap leaves the puzzle
    exactly as it was, still in the queue. The edits are held by the UI until
    the reviewer approves, at which point `approve` stores them -- so there is
    no fourth state for "edited but undecided".
    """
    rows, decisions = _load_pair(cfg, hash_)
    if hash_ in decisions and decisions[hash_].verdict == dec.REJECT:
        raise BadRequest("that puzzle is rejected -- undo the verdict first")

    bank = _replay(cfg, graph, rows[hash_], edits)
    solution = set(rows[hash_]["solution"])
    return {
        "hash": hash_,
        "bank": list(bank),
        "decoys": [w for w in bank if w not in solution],
        "bankEdits": [{"removed": e.removed, "added": e.added} for e in edits],
    }


def swap_options(
    cfg: Config,
    graph: nx.Graph,
    hash_: str,
    removed: str,
    edits: tuple[dec.BankEdit, ...] = (),
    limit: int = 8,
) -> dict:
    """Replacements for one decoy that the engine would actually accept.

    Without these a reviewer types a word and hopes, and most guesses are
    refused for reasons they cannot see from outside. Each option carries its
    temptingness and the strategy that proposed it, so softening a bank --
    round 1's actual complaint -- is a visible move rather than a shot in the
    dark.
    """
    rows, _ = _load_pair(cfg, hash_)
    row = rows[hash_]
    bank = _replay(cfg, graph, row, edits)
    if removed not in bank:
        raise BadRequest(f"{removed!r} is not in the bank")

    options = distractors.safe_swaps(
        cfg, graph, _STEMMER, _path_from_row(row), bank, removed, limit=limit
    )
    return {
        "hash": hash_,
        "removed": removed,
        "options": [
            {"word": o.word, "temptingness": round(o.temptingness, 2), "source": o.source}
            for o in options
        ],
    }


# --------------------------------------------------------------------------
# 6c -- the approved pool, and choosing a date (planning.md 16.2, 16.6)
# --------------------------------------------------------------------------


def _slot_dates(cfg: Config, first_date: str) -> list[str]:
    """The contiguous run a reviewer may schedule into.

    Dates are not free-form. The archive's one hard invariant is
    `date == epoch + (id - 1)` days, so a puzzle does not sit on an arbitrary
    day -- it occupies a slot in an unbroken run. Offering the run instead of a
    date picker makes a gap impossible to create by hand.
    """
    start = date.fromisoformat(first_date)
    return [(start + timedelta(days=i)).isoformat() for i in range(cfg.batch_size)]


def _scheduled_as_puzzles(
    rows: dict[str, dict],
    decisions: dict[str, dec.Decision],
    skip: str | None = None,
):
    """Scheduled decisions rendered as `Puzzle`s, so the corpus rules can see
    them beside the archive.

    Ids are negative placeholders: these puzzles have no number until export
    assigns one, and the three corpus rules care about words, endpoint pairs
    and chains -- none of which depend on it.
    """
    from ..domain.models import Puzzle

    ordered = sorted(
        ((h, d) for h, d in decisions.items() if d.is_scheduled and h in rows),
        key=lambda pair: pair[1].date or "",
    )
    out = []
    for offset, (hash_, decision) in enumerate(ordered):
        if hash_ == skip:
            continue
        row = rows[hash_]
        out.append(
            Puzzle(
                id=-(offset + 1),
                date=decision.date or "",
                start=row["start"],
                end=row["end"],
                solution=tuple(row["solution"]),
                bank=dec.apply_edits(row["bank"], decision.bank_edits),
            )
        )
    return out


def pool(cfg: Config) -> dict:
    """Everything approved, and the dates it can go on.

    Scheduled first in date order, then the undated pool best-first. Both
    halves of the state 16.2 exists to create, on one screen, because the
    question a reviewer is actually answering is always "what goes next".
    """
    rows = {r["hash"]: r for r in exporters.read_candidates(cfg.candidates_path)}
    decisions = exporters.read_decisions(cfg.decisions_path)
    archive = exporters.read_archive(cfg)
    _, first_date = exporters.next_slot(archive, cfg.epoch_date)

    try:
        taken = dec.taken_dates(decisions)
    except dec.DecisionError as exc:
        raise BadRequest(str(exc)) from exc

    split = dec.split(decisions)
    scheduled = [
        _candidate_view(rows[h], decisions[h]) for h in split.scheduled if h in rows
    ]
    pooled = sorted(
        (_candidate_view(rows[h], decisions[h]) for h in split.approved_pool if h in rows),
        key=lambda v: (-(v["quality"] or 0.0), v["hash"]),
    )

    return {
        "scheduled": scheduled,
        "pooled": pooled,
        "slots": [{"date": d, "hash": taken.get(d)} for d in _slot_dates(cfg, first_date)],
        "archive": {
            "count": len(archive),
            "lastDate": archive[-1].date if archive else None,
            "nextDate": first_date,
        },
    }


def schedule(cfg: Config, hash_: str, when: str) -> dict:
    """Put an approved puzzle on a date, with the corpus warning attached.

    The warning is 16.6's whole argument: the checks that fail loudly at export
    (7.7.1), asked while the reviewer can still pick a different day. It never
    blocks -- export keeps the hard gate, and this is what stops it firing.
    """
    rows, decisions = _load_pair(cfg, hash_)
    decision = decisions.get(hash_)
    if decision is None or decision.verdict != dec.ACCEPT:
        raise BadRequest("only an approved puzzle can be scheduled")

    archive = exporters.read_archive(cfg)
    _, first_date = exporters.next_slot(archive, cfg.epoch_date)
    slots = _slot_dates(cfg, first_date)
    if when not in slots:
        raise BadRequest(
            f"{when} is not an open slot -- pick between {slots[0]} and {slots[-1]}"
        )
    holder = dec.taken_dates(decisions).get(when)
    if holder is not None and holder != hash_:
        raise BadRequest(f"{when} already holds {holder}")

    try:
        decisions[hash_] = dec.schedule(decision, when)
    except dec.DecisionError as exc:
        raise BadRequest(str(exc)) from exc

    row = rows[hash_]
    bank = dec.apply_edits(row["bank"], decision.bank_edits)
    warnings = corpus.warnings_for(
        {*bank, row["start"], row["end"]},
        row["start"],
        row["end"],
        row["solution"],
        context=[*archive, *_scheduled_as_puzzles(rows, decisions, skip=hash_)],
        max_word_reuse=cfg.max_word_reuse,
        window=cfg.word_reuse_window,
    )

    exporters.write_decisions(cfg.decisions_path, decisions)
    return {"hash": hash_, "date": when, "warnings": warnings}


def unschedule(cfg: Config, hash_: str) -> dict:
    """Back to the undated pool.

    Deliberately not the same act as unapproving: the reviewer still likes the
    puzzle, they just want a different day for it.
    """
    _, decisions = _load_pair(cfg, hash_)
    decision = decisions.get(hash_)
    if decision is None:
        raise BadRequest("that puzzle has no verdict")
    try:
        decisions[hash_] = dec.unschedule(decision)
    except dec.DecisionError as exc:
        raise BadRequest(str(exc)) from exc

    exporters.write_decisions(cfg.decisions_path, decisions)
    return {"hash": hash_, "date": None}
