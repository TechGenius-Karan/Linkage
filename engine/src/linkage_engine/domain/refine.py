"""Hand-edited puzzles, and the one thing the machine still gets to refuse.

Domain tier: pure.

The reviewer decides whether a puzzle holds (docs/admin.md 11). ConceptNet is
wrong often enough that most rejections say so outright, and a tool that accepts
a verdict on the generator's output while refusing the correction -- because the
dataset just overruled lacks the edge -- has the authority backwards.

So this module splits the checks into two piles that are *not* the same kind of
question:

    REFUSED    a second valid ordering exists, or a chord creates one.
               Arithmetic over 7,920 arrangements. Nobody can see it by eye,
               and getting it wrong means a player arranges the board correctly
               and is told they are wrong (planning.md 2.3).

    REPORTED   a rung ConceptNet does not carry; a bank the generator would
               not have built. Told to the reviewer, never blocking, because
               these are matters of judgement and the judgement is theirs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from ..config import Config
from .decisions import ManualEdge, Puzzle
from .distractors import overlaps_substring, shares_stem
from .models import Path
from .pathfinder import has_chord
from .ports import Stemmer
from .validator import chain_is_valid, solve_all

#: Weight given to a link the reviewer asserted. `hints.obviousness()` ranks
#: answer words by the strength of the links either side, so a hand edge needs
#: *some* number; this says "ordinary", which is all anyone knows about it.
ASSERTED_WEIGHT = 2.0

#: What a hand-asserted edge reports as its relation.
ASSERTED_RELATION = "AssertedByReviewer"


@dataclass(frozen=True, slots=True)
class Verdict:
    """What the machine has to say about an edited puzzle.

    `refusals` is empty or the puzzle cannot ship. `notes` never blocks -- it is
    the tool telling the reviewer what it noticed, which they are free to
    overrule and usually should be.
    """

    refusals: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    #: Rungs, 0..4, now resting on the reviewer's word rather than ConceptNet's.
    asserted_links: tuple[int, ...] = ()
    #: Rungs with no link at all, from either source. Structured rather than
    #: only described in `refusals`, because the UI offers to assert each one
    #: and parsing prose to find them would be absurd.
    broken_links: tuple[int, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.refusals


def augmented(graph: nx.Graph, edges: tuple[ManualEdge, ...]) -> nx.Graph:
    """The graph plus whatever the reviewer asserted.

    A **view over a copy**, not a mutation: the server holds one graph for its
    whole life, and an edit previewed and then abandoned must not leave a link
    behind for the next puzzle to trip over.

    Copying edges is cheap here because only the six nodes of one puzzle and
    their neighbours are ever consulted -- but `nx.Graph.copy()` on the full
    graph would not be, so this builds a subgraph view instead when it can.
    """
    if not edges:
        return graph
    touched = {w for a, b, _ in edges for w in (a, b)}
    for a, b, _ in edges:
        touched.update(graph[a] if a in graph else ())
        touched.update(graph[b] if b in graph else ())
    local = nx.Graph(graph.subgraph(touched & set(graph)))
    for a, b, weight in edges:
        local.add_edge(a, b, weight=weight, relations=(ASSERTED_RELATION,))
    # Compose so the rest of the graph is still reachable for the uniqueness
    # sweep, which looks at bank words that may sit outside `touched`.
    return nx.compose(graph, local)


def effective_path(
    graph: nx.Graph, puzzle: Puzzle, edges: tuple[ManualEdge, ...] = ()
) -> Path:
    """Rebuild the chain's weights and relations from the graph it actually has.

    After a hand edit the stored weights are stale -- they describe rungs that
    no longer exist. `hints.obviousness()` ranks answer words by those weights,
    so shipping the old numbers would pick the wrong words to offer as hints.
    """
    g = augmented(graph, edges)
    nodes = puzzle.nodes
    weights: list[float] = []
    relations: list[tuple[str, ...]] = []
    for a, b in zip(nodes, nodes[1:]):
        data = g.get_edge_data(a, b)
        weights.append(float(data["weight"]) if data else ASSERTED_WEIGHT)
        relations.append(tuple(data.get("relations", ())) if data else ())
    return Path(
        start=puzzle.start,
        end=puzzle.end,
        steps=puzzle.solution,
        weights=tuple(weights),
        relations=tuple(relations),
    )


def unattested_links(graph: nx.Graph, puzzle: Puzzle) -> tuple[int, ...]:
    """Rungs ConceptNet has no edge for, by index.

    Not an error. The reviewer is told so they know they are the source for
    that link, which is worth knowing while deciding (docs/admin.md 11.2).
    """
    nodes = puzzle.nodes
    return tuple(
        i for i, (a, b) in enumerate(zip(nodes, nodes[1:])) if not graph.has_edge(a, b)
    )


def _word_problems(word: str, cfg: Config) -> str | None:
    """Whatever would stop this word shipping as a tile.

    Normalisation is not a matter of taste: the codec, the client and the
    generator all assume the same shape, and a word that breaks it breaks the
    file format rather than the puzzle.
    """
    if not word.isascii() or not word.isalpha() or not word.islower():
        return f"{word!r} must be lowercase a-z only"
    if not cfg.word_min_len <= len(word) <= cfg.word_max_len:
        return f"{word!r} must be {cfg.word_min_len}-{cfg.word_max_len} letters"
    return None


def validate_puzzle(
    cfg: Config,
    graph: nx.Graph,
    stemmer: Stemmer,
    puzzle: Puzzle,
    manual_edges: tuple[ManualEdge, ...] = (),
) -> Verdict:
    """Everything the machine can say about a hand-edited puzzle.

    Asked identically by the editor, by `approve`, and by `export`, so a puzzle
    cannot pass one and fail another.
    """
    refusals: list[str] = []
    notes: list[str] = []
    g = augmented(graph, manual_edges)
    nodes = puzzle.nodes

    # -- shape: these are file-format facts, not judgement -----------------
    for word in {*nodes, *puzzle.bank}:
        problem = _word_problems(word, cfg)
        if problem:
            refusals.append(problem)

    if len(puzzle.solution) != cfg.chain_length:
        refusals.append(
            f"a chain is {cfg.chain_length} words, got {len(puzzle.solution)}"
        )
    missing = [w for w in puzzle.solution if w not in puzzle.bank]
    if missing:
        refusals.append(f"the bank is missing its own answer: {', '.join(missing)}")
    if len(set(puzzle.bank)) != len(puzzle.bank):
        refusals.append("the bank has a duplicate word")
    if not cfg.bank_size_min <= len(puzzle.bank) <= 12:
        refusals.append(
            f"a bank is {cfg.bank_size_min}-12 words, got {len(puzzle.bank)}"
        )
    if puzzle.start in puzzle.bank or puzzle.end in puzzle.bank:
        refusals.append("an endpoint is also sitting in the bank")

    if refusals:
        # The graph checks below would report nonsense on a malformed puzzle.
        return Verdict(refusals=tuple(refusals))

    # -- the chain must exist, somewhere ----------------------------------
    broken = [
        i
        for i, (a, b) in enumerate(zip(nodes, nodes[1:]))
        if not g.has_edge(a, b)
    ]
    if broken:
        pairs = ", ".join(f"{nodes[i]} -> {nodes[i + 1]}" for i in broken)
        refusals.append(
            f"no link for {pairs}. Assert it if you know it holds, or pick "
            "another word."
        )
        return Verdict(refusals=tuple(refusals), broken_links=tuple(broken))

    assert chain_is_valid(g, puzzle.start, puzzle.end, puzzle.solution)

    # -- the two the machine refuses --------------------------------------
    if cfg.enforce_chordless and has_chord(g, nodes):
        refusals.append(
            "two of these six words link directly, which gives the player a "
            "shortcut past a rung"
        )

    solutions = solve_all(
        g, puzzle.start, puzzle.end, puzzle.bank, cfg.chain_length, limit=2
    )
    if len(solutions) > 1:
        other = " -> ".join(next(s for s in solutions if s != puzzle.solution))
        refusals.append(f"a second arrangement also works: {other}")
    elif not solutions:
        refusals.append("this bank has no valid arrangement at all")

    # -- the ones it only mentions ----------------------------------------
    asserted = unattested_links(graph, puzzle)
    for i in asserted:
        notes.append(
            f"{nodes[i]} -> {nodes[i + 1]} rests on your word, not ConceptNet's"
        )

    frozen = frozenset(puzzle.bank) | {puzzle.start, puzzle.end}
    for word in sorted(puzzle.bank):
        rest = frozenset(frozen - {word})
        if shares_stem(stemmer, word, rest):
            notes.append(f"{word!r} shares a stem with another word on screen")
        elif overlaps_substring(word, rest):
            notes.append(f"{word!r} contains, or sits inside, another word on screen")

    return Verdict(
        refusals=tuple(refusals),
        notes=tuple(notes),
        asserted_links=asserted,
    )
