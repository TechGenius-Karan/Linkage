"""The human curation gate (planning.md 7.7).

Presentation tier.

ConceptNet is noisy, and algorithmically valid is not the same as fun. The
chain `cat -> animal -> thing -> object -> box` passes every automated check
in this engine and is still a bad puzzle. Nothing operating purely on graph
structure closes that gap.

Phase 1 measurement sharpened the point: yield is ~4.57M usable paths per
1,000 seeds against a threshold of 3. Finding paths is free. This screen is
where the actual product decisions get made.
"""

from __future__ import annotations

from dataclasses import dataclass

import typer

ACCEPT, REJECT, SKIP = "accept", "reject", "skip"


@dataclass(frozen=True, slots=True)
class ReviewStats:
    accepted: int
    rejected: int
    skipped: int
    remaining: int


def render(candidate: dict, index: int, total: int, decided: int) -> None:
    """One candidate, laid out so a person can judge it in a few seconds."""
    start, end = candidate["start"].upper(), candidate["end"].upper()
    solution = candidate["solution"]
    weights = candidate["weights"]

    typer.echo("\n" + "=" * 72)
    typer.secho(
        f"  {index}/{total}   quality {candidate['quality']:.2f}   "
        f"approved so far: {decided}",
        fg=typer.colors.BRIGHT_BLACK,
    )
    typer.echo()

    chain = f"  {start} -> " + " -> ".join(solution) + f" -> {end}"
    typer.secho(chain, fg=typer.colors.CYAN, bold=True)

    # Edge weights, aligned under the gap each one spans.
    gutter = " " * (4 + len(start))
    typer.secho(
        gutter + "   ".join(f"{w:.1f}" for w in weights), fg=typer.colors.BRIGHT_BLACK
    )

    solution_set = set(solution)
    distractors = [w for w in candidate["bank"] if w not in solution_set]
    typer.echo()
    typer.echo(f"  distractors:  {'  '.join(distractors)}")

    relations = {r for group in candidate["relations"] for r in group}
    typer.secho(f"  relations:    {', '.join(sorted(relations))}", fg=typer.colors.BRIGHT_BLACK)


def prompt() -> str:
    """Single keypress verdict. `q` aborts and keeps everything decided so far."""
    while True:
        raw = typer.prompt("  [a]ccept  [r]eject  [s]kip  [q]uit", default="a").strip().lower()
        if raw in ("a", "accept"):
            return ACCEPT
        if raw in ("r", "reject"):
            return REJECT
        if raw in ("s", "skip"):
            return SKIP
        if raw in ("q", "quit"):
            return "quit"
        typer.secho("  ? use a, r, s or q", fg=typer.colors.YELLOW)
