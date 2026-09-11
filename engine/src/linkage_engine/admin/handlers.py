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
from ..domain import refine


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
        "bankEdits": _edits_json(edits),
        "manualEdges": [list(e) for e in (decision.manual_edges if decision else ())],
        "date": decision.date if decision is not None else None,
    }


def _edits_json(edits: tuple[dec.WordEdit, ...]) -> list[dict]:
    return [
        {
            "field": e.field,
            "removed": e.removed,
            "added": e.added,
            **({"index": e.index} if e.index is not None else {}),
        }
        for e in edits
    ]


def read_edits(raw: object) -> tuple[dec.WordEdit, ...]:
    """Parse hand edits. `field` defaults to "bank", which every edit was
    before hand editing existed."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise BadRequest("edits must be a list")
    out: list[dec.WordEdit] = []
    for entry in raw:
        if not isinstance(entry, dict) or not entry.get("added"):
            raise BadRequest("each edit needs a replacement word")
        try:
            out.append(
                dec.WordEdit(
                    field=entry.get("field", "bank"),
                    removed=str(entry.get("removed", "")),
                    added=str(entry["added"]),
                    index=entry.get("index"),
                )
            )
        except dec.DecisionError as exc:
            raise BadRequest(str(exc)) from exc
    return tuple(out)


#: How many candidates the review screen holds at once (docs/admin.md 10.3).
#: Five is the largest window that needs no client-side bookkeeping: the queue
#: is sorted deterministically, so "the first five pending" after a verdict is
#: by construction the four survivors in their original order plus one arrival.
QUEUE_WINDOW = 5

#: Open days surfaced on the schedule screen (docs/admin.md 12.2). A week is
#: the unit a person plans in; the whole thirty-day run is a wall.
OPEN_DAYS = 7


def queue(cfg: Config, *, limit: int | None = QUEUE_WINDOW) -> dict:
    """Candidates with no verdict yet, hardest-first by quality.

    The ordering is the scorer's, and `docs/engine.md` 7.7.2 is candid that it
    barely beats chance -- but a queue ordered badly is still a queue, and
    stable ordering matters more here than good ordering: a reviewer who
    reloads must not lose their place, and the five-card window depends on it.

    `returned` is a separate lane, not part of the window. A puzzle sent back
    from the pool is one the reviewer already chose; letting it fall into 867
    pending candidates would be losing it (docs/admin.md 12.1).
    """
    rows = exporters.read_candidates(cfg.candidates_path)
    decisions = exporters.read_decisions(cfg.decisions_path)

    pending = [r for r in rows if r["hash"] not in decisions]
    pending.sort(key=lambda r: (-(r.get("quality") or 0.0), r["hash"]))

    split = dec.split(decisions)
    by_hash = {r["hash"]: r for r in rows}
    return {
        "puzzles": [_candidate_view(r) for r in pending[:limit]],
        "returned": [
            _candidate_view(by_hash[h], decisions[h])
            for h in split.returned
            if h in by_hash
        ],
        "counts": {
            "total": len(rows),
            "pending": len(pending),
            "decided": len(decisions) - len(split.returned),
            "approved": len(split.approved_pool) + len(split.scheduled),
            "scheduled": len(split.scheduled),
            "rejected": len(split.rejected),
            "returned": len(split.returned),
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
    edits: tuple[dec.WordEdit, ...] = (),
    manual_edges: tuple[dec.ManualEdge, ...] = (),
    graph: nx.Graph | None = None,
) -> dict:
    """Record that the reviewer wants this puzzle, with any hand edits.

    The edits ride along with the approval rather than being a write of their
    own, so there is no fourth state for "edited but undecided" -- a swap is a
    preview until the reviewer commits to the puzzle it produced.

    They are re-proved here even though `edit` already proved them. The check
    is 60ms and this is the one property the whole game rests on; a client that
    skipped the preview must not be able to talk its way past it.
    """
    rows, decisions = _load_pair(cfg, hash_)
    existing = decisions.get(hash_)
    # A puzzle sent back for another look is *meant* to be re-decided; anything
    # else with a verdict is not (docs/admin.md 12.1).
    if existing is not None and not existing.is_returned:
        raise BadRequest("that puzzle already has a verdict")
    if (edits or manual_edges) and graph is not None:
        _, verdict = _check(cfg, graph, rows[hash_], edits, manual_edges)
        if not verdict.ok:
            raise BadRequest("; ".join(verdict.refusals))

    decisions[hash_] = dec.approve(_today(), edits=edits, manual_edges=manual_edges)
    exporters.write_decisions(cfg.decisions_path, decisions)
    # Approving records taste and schedules nothing (planning.md 16.2). The
    # response says so explicitly so the UI cannot imply otherwise.
    return {"hash": hash_, "verdict": dec.ACCEPT, "date": None}


def reject(cfg: Config, hash_: str, reason: str, bad_link: int | None = None) -> dict:
    _, decisions = _load_pair(cfg, hash_)
    existing = decisions.get(hash_)
    if existing is not None and not existing.is_returned:
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


def send_back(cfg: Config, hash_: str) -> dict:
    """Return an approved puzzle to the review queue (docs/admin.md 12.1).

    Named `send_back` rather than `revisit` only because the domain owns that
    verb; the endpoint is `/api/admin/revisit`.

    Distinct from `undo`, which deletes the verdict outright and drops the
    puzzle back among the 867 pending. This keeps a record, so the puzzle
    lands in its own lane where the reviewer can actually find it again.
    """
    _, decisions = _load_pair(cfg, hash_)
    decision = decisions.get(hash_)
    if decision is None:
        raise BadRequest("that puzzle has no verdict")
    try:
        decisions[hash_] = dec.revisit(_today(), decision)
    except dec.DecisionError as exc:
        raise BadRequest(str(exc)) from exc

    exporters.write_decisions(cfg.decisions_path, decisions)
    return {"hash": hash_, "verdict": dec.REVISIT}


# --------------------------------------------------------------------------
# 6b -- refining a bank, with the engine holding a veto (planning.md 16.4)
# --------------------------------------------------------------------------

#: One instance, because the Porter stemmer memoises and a swap asks it about
#: the same eleven words over and over.
_STEMMER = PorterStemmerAdapter()


def read_edges(raw: object) -> tuple[dec.ManualEdge, ...]:
    """Links the reviewer asserted (docs/admin.md 11.2)."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise BadRequest("manualEdges must be a list")
    out: list[dec.ManualEdge] = []
    for entry in raw:
        if not isinstance(entry, (list, tuple)) or len(entry) not in (2, 3):
            raise BadRequest("each asserted link is [from, to] or [from, to, weight]")
        weight = float(entry[2]) if len(entry) == 3 else refine.ASSERTED_WEIGHT
        out.append((str(entry[0]), str(entry[1]), weight))
    return tuple(out)


def _effective(
    row: dict, edits: tuple[dec.WordEdit, ...]
) -> dec.Puzzle:
    try:
        return dec.apply_puzzle_edits(
            row["start"], row["end"], row["solution"], row["bank"], edits
        )
    except dec.DecisionError as exc:
        raise BadRequest(str(exc)) from exc


def _check(
    cfg: Config,
    graph: nx.Graph,
    row: dict,
    edits: tuple[dec.WordEdit, ...],
    manual_edges: tuple[dec.ManualEdge, ...],
) -> tuple[dec.Puzzle, refine.Verdict]:
    puzzle = _effective(row, edits)
    verdict = refine.validate_puzzle(cfg, graph, _STEMMER, puzzle, manual_edges)
    return puzzle, verdict


def edit(
    cfg: Config,
    graph: nx.Graph,
    hash_: str,
    edits: tuple[dec.WordEdit, ...],
    manual_edges: tuple[dec.ManualEdge, ...] = (),
) -> dict:
    """Preview a hand edit. Proves it, and **writes nothing**.

    Generalises the old `swap`, which could only touch decoys. Any word may
    change now -- the reviewer's judgement is the authority on whether a chain
    reads (docs/admin.md 11) -- and the machine keeps exactly one veto:
    uniqueness, plus the chords that manufacture it.

    Refusals block approval. Notes do not: they are the tool saying what it
    noticed, including which rungs now rest on the reviewer's word rather than
    ConceptNet's, and the reviewer is free to overrule all of it.
    """
    rows, decisions = _load_pair(cfg, hash_)
    if hash_ in decisions and decisions[hash_].verdict == dec.REJECT:
        raise BadRequest("that puzzle is rejected -- undo the verdict first")

    puzzle, verdict = _check(cfg, graph, rows[hash_], edits, manual_edges)
    solution = set(puzzle.solution)
    return {
        "hash": hash_,
        "start": puzzle.start,
        "end": puzzle.end,
        "solution": list(puzzle.solution),
        "chain": list(puzzle.nodes),
        "bank": list(puzzle.bank),
        "decoys": [w for w in puzzle.bank if w not in solution],
        "refusals": list(verdict.refusals),
        "notes": list(verdict.notes),
        "assertedLinks": list(verdict.asserted_links),
        "brokenLinks": list(verdict.broken_links),
        "ok": verdict.ok,
        "bankEdits": _edits_json(edits),
        "manualEdges": [list(e) for e in manual_edges],
    }


def swap_options(
    cfg: Config,
    graph: nx.Graph,
    hash_: str,
    removed: str,
    edits: tuple[dec.WordEdit, ...] = (),
    manual_edges: tuple[dec.ManualEdge, ...] = (),
    limit: int = 8,
) -> dict:
    """Replacements for one decoy that the engine would actually accept.

    Without these a reviewer types a word and hopes; most guesses are refused
    for reasons they cannot see from outside. Each option carries its
    temptingness and the strategy that proposed it, so softening a bank --
    round 1's actual complaint -- is a visible move rather than a shot in the
    dark.

    Computed against the *effective* puzzle, so a reviewer who has already
    rewritten an answer word gets suggestions for the chain they now have.
    """
    rows, _ = _load_pair(cfg, hash_)
    row = rows[hash_]
    puzzle = _effective(row, edits)
    if removed not in puzzle.bank:
        raise BadRequest(f"{removed!r} is not in the bank")
    if removed in puzzle.solution:
        raise BadRequest(f"{removed!r} is an answer word, not a decoy")

    g = refine.augmented(graph, manual_edges)
    path = refine.effective_path(graph, puzzle, manual_edges)
    options = distractors.safe_swaps(
        cfg, g, _STEMMER, path, puzzle.bank, removed, limit=limit
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

    slots = [{"date": d, "hash": taken.get(d)} for d in _slot_dates(cfg, first_date)]
    return {
        "scheduled": scheduled,
        "pooled": pooled,
        "slots": slots,
        # A week is the unit a person plans in, and thirty chips is a wall. The
        # full run stays in `slots` for anyone who wants it (docs/admin.md 12.2).
        "openDays": [s["date"] for s in slots if s["hash"] is None][:OPEN_DAYS],
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
