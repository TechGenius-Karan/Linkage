"""Admin request handlers (planning.md 16.3).

Presentation tier: parse a request, call the domain, return JSON. No HTTP types
appear here -- `server.py` owns those -- so every handler is a plain function
call in a test.
"""

from __future__ import annotations

from datetime import date

from ..config import Config
from ..data import exporters
from ..domain import decisions as dec


class BadRequest(ValueError):
    """The reviewer asked for something impossible. Becomes a 400 with the text."""


def _today() -> str:
    return date.today().isoformat()


def _candidate_view(row: dict, weights_first: bool = True) -> dict:
    """One candidate, shaped for the queue.

    `chain` is the whole ladder including the endpoints, and `linkWeights` runs
    parallel to it -- so the UI can put a weight *between* two words without
    recomputing anything. That pairing is what makes marking a bad link
    (planning.md 16.2) a click rather than a guess.
    """
    solution = list(row["solution"])
    chain = [row["start"], *solution, row["end"]]
    bank = list(row["bank"])
    return {
        "hash": row["hash"],
        "start": row["start"],
        "end": row["end"],
        "solution": solution,
        "chain": chain,
        "decoys": [w for w in bank if w not in set(solution)],
        "bank": bank,
        "quality": row.get("quality"),
        "linkWeights": list(row.get("weights", ())) if weights_first else [],
        "relations": [list(r) for r in row.get("relations", ())],
    }


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


def approve(cfg: Config, hash_: str) -> dict:
    _, decisions = _load_pair(cfg, hash_)
    if hash_ in decisions:
        raise BadRequest("that puzzle already has a verdict")

    decisions[hash_] = dec.approve(_today())
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
