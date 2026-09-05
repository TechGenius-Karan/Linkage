"""Writing the archive to disk (planning.md 3.1-3.3, 7.10).

Data tier: filesystem only.

Three outputs, and they go to two different places on purpose:

    web/public/puzzles/<date>.json   obfuscated, served to players
    web/public/puzzles/manifest.json plain, served
    engine/fixtures/verification-subgraph.json
                                     PLAINTEXT ANSWER KEY -- never served
"""

from __future__ import annotations

import itertools
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Sequence

import networkx as nx

from ..config import Config
from ..domain.models import Candidate, Puzzle
from .codec import encode


def _write_json(path: Path, payload: object, *, indent: int | None = 2) -> None:
    """Sorted keys and a trailing newline, so a regenerated file diffs cleanly."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, indent=indent, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Candidates and review decisions
# --------------------------------------------------------------------------


def candidate_to_dict(candidate: Candidate) -> dict:
    return {
        "hash": candidate.content_hash(),
        "start": candidate.path.start,
        "end": candidate.path.end,
        "solution": list(candidate.path.steps),
        "bank": list(candidate.bank),
        "quality": candidate.quality,
        "weights": [round(w, 3) for w in candidate.path.weights],
        "relations": [list(r) for r in candidate.path.relations],
        "scores": dict(candidate.score_breakdown),
    }


def write_candidates(path: Path, candidates: Sequence[Candidate]) -> None:
    """Ranked best-first, so `review` shows the strongest puzzles early."""
    ordered = sorted(candidates, key=lambda c: (-c.quality, c.content_hash()))
    write_candidate_rows(path, [candidate_to_dict(c) for c in ordered])


def write_candidate_rows(path: Path, rows: Sequence[dict]) -> None:
    """Write already-serialised candidate rows, ranked best-first.

    Used when merging a fresh run into candidates already on disk, where the
    rows never became `Candidate` objects in the first place.
    """
    ordered = sorted(rows, key=lambda r: (-r["quality"], r["hash"]))
    _write_json(path, list(ordered))


def read_candidates(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"No candidates at {path}\nGenerate some first:\n    linkage generate"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def read_decisions(path: Path) -> dict[str, str]:
    """Review verdicts keyed by content hash.

    Kept separate from candidates.json so re-running `generate` never
    discards a judgement a person already made (planning.md 7.7).
    """
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_decisions(path: Path, decisions: dict[str, str]) -> None:
    _write_json(path, decisions)


# --------------------------------------------------------------------------
# The shipped archive
# --------------------------------------------------------------------------


def read_archive(cfg: Config) -> list[Puzzle]:
    """Every puzzle already shipped, decoded from its per-day file.

    Building a year one month at a time means every later batch has to know
    what the earlier ones used -- for word reuse, for date continuity, and
    for puzzle numbering.
    """
    from .codec import decode

    if not cfg.puzzles_dir.exists():
        return []

    puzzles: list[Puzzle] = []
    for path in sorted(cfg.puzzles_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        row = decode(json.loads(path.read_text(encoding="utf-8"))["d"], path.stem)
        puzzles.append(
            Puzzle(
                id=row["id"],
                date=row["date"],
                start=row["start"],
                end=row["end"],
                solution=tuple(row["solution"]),
                bank=tuple(row["bank"]),
            )
        )
    return sorted(puzzles, key=lambda p: p.id)


def next_slot(existing: Sequence[Puzzle], epoch_date: str) -> tuple[int, str]:
    """Where the next batch starts: `(first_id, first_date)`.

    An empty archive starts at id 1 on the epoch; otherwise the batch picks
    up the day after the last shipped puzzle, with no gap and no renumbering.
    """
    if not existing:
        return 1, epoch_date
    last = existing[-1]
    following = date.fromisoformat(last.date) + timedelta(days=1)
    return last.id + 1, following.isoformat()


def assign_dates(
    approved: Sequence[Candidate], start_date: str, first_id: int = 1
) -> list[Puzzle]:
    """Turn approved candidates into dated, numbered puzzles.

    `date` must equal `EPOCH_DATE + (id - 1)` days -- the golden test asserts
    it, because a drift between id and date shows the wrong puzzle number in
    every share.
    """
    epoch = date.fromisoformat(start_date)
    puzzles: list[Puzzle] = []
    for offset, candidate in enumerate(approved):
        puzzles.append(
            Puzzle(
                id=first_id + offset,
                date=(epoch + timedelta(days=offset)).isoformat(),
                start=candidate.path.start,
                end=candidate.path.end,
                solution=candidate.path.steps,
                bank=candidate.bank,
            )
        )
    return puzzles


def write_puzzles(cfg: Config, puzzles: Iterable[Puzzle]) -> list[Path]:
    """One obfuscated file per day, keyed by its own date."""
    written: list[Path] = []
    for puzzle in puzzles:
        path = cfg.puzzles_dir / f"{puzzle.date}.json"
        _write_json(
            path,
            {
                "v": cfg.schema_version,
                "d": encode(puzzle.to_payload(cfg.schema_version), puzzle.date),
            },
            indent=None,
        )
        written.append(path)
    return written


def write_manifest(cfg: Config, puzzles: Sequence[Puzzle]) -> Path:
    """Lets the client compute the puzzle number and detect 'no puzzle today'
    without a 404 round-trip (planning.md 3.3)."""
    path = cfg.puzzles_dir / "manifest.json"
    _write_json(
        path,
        {
            "schemaVersion": cfg.schema_version,
            "epoch": puzzles[0].date if puzzles else cfg.epoch_date,
            "count": len(puzzles),
            "firstId": puzzles[0].id if puzzles else 1,
        },
    )
    return path


def write_licence_notice(cfg: Config) -> Path:
    """ConceptNet is CC BY-SA 4.0, so the derived data is too (planning.md 12.2)."""
    path = cfg.puzzles_dir / "LICENSE.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "Linkage puzzle data\n"
        "===================\n\n"
        "These puzzles are derived from ConceptNet 5.7 (https://conceptnet.io),\n"
        "which is licensed under Creative Commons Attribution-ShareAlike 4.0\n"
        "International (CC BY-SA 4.0).\n\n"
        "This derived data is therefore distributed under the same licence:\n"
        "https://creativecommons.org/licenses/by-sa/4.0/\n\n"
        "The Linkage source code is MIT licensed; see the repository root.\n",
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------
# Verification subgraph (planning.md 7.10)
# --------------------------------------------------------------------------


def build_verification_subgraph(
    graph: nx.Graph, puzzles: Sequence[Puzzle]
) -> list[list]:
    """The **induced** subgraph over every puzzle's bank plus its endpoints.

    Induced is the whole point. Exporting only the five solution edges would
    make the uniqueness test vacuous -- it would find one solution because it
    was handed exactly one solution's worth of edges, and would pass while
    proving nothing. Every edge among those 13 nodes goes in, so an alternate
    chain, if one existed, would be visible.
    """
    edges: dict[tuple[str, str], float] = {}
    for puzzle in puzzles:
        nodes = sorted({*puzzle.bank, puzzle.start, puzzle.end})
        for a, b in itertools.combinations(nodes, 2):
            data = graph.get_edge_data(a, b)
            if data is not None:
                edges[(a, b)] = data["weight"]
    return [[a, b, round(w, 4)] for (a, b), w in sorted(edges.items())]


def write_verification_subgraph(
    cfg: Config, graph: nx.Graph, puzzles: Sequence[Puzzle]
) -> Path:
    _write_json(
        cfg.subgraph_path,
        {
            "schemaVersion": cfg.schema_version,
            "note": (
                "Induced subgraph over every shipped puzzle's bank + endpoints. "
                "Verification only. Plaintext answer key -- never serve this."
            ),
            "edges": build_verification_subgraph(graph, puzzles),
        },
    )
    return cfg.subgraph_path


def read_verification_subgraph(path: Path) -> nx.Graph:
    """Rebuild a graph from the fixture, for tests that must not touch the dump."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    graph = nx.Graph()
    for a, b, weight in payload["edges"]:
        graph.add_edge(a, b, weight=weight)
    return graph
