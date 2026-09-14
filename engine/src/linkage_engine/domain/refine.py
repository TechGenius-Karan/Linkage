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
from .decisions import CHAIN_LINKS, ManualEdge, Puzzle
from .distractors import overlaps_substring, shares_stem
from .hubs import sorted_neighbours
from .models import Path
from .pathfinder import has_chord
from .ports import Stemmer
from .validator import chain_is_valid, is_uniquely_solvable, solve_all

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


@dataclass(frozen=True, slots=True)
class LinkFix:
    """One candidate replacement for the solution word at `index`."""

    index: int  # which rung, 0..3, this replaces
    word: str
    temptingness: float
    source: str


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


def safe_link_fixes(
    cfg: Config,
    graph: nx.Graph,
    stemmer: Stemmer,
    puzzle: Puzzle,
    bad_link: int,
    manual_edges: tuple[ManualEdge, ...] = (),
    limit: int = 8,
) -> list[LinkFix]:
    """Replacements for the solution word(s) touching a flagged link.

    `distractors.safe_swaps` generalised from decoys to the chain itself: the
    same two invariants (chordless, uniquely solvable), the same "never offer
    the unsafe one" contract -- this just searches a solution slot instead of
    the bank.

    Rung `j` (0..3) sits at `nodes[j + 1]`, between `nodes[j]` and
    `nodes[j + 2]`. Link `bad_link` (0..4) sits between `nodes[bad_link]` and
    `nodes[bad_link + 1]`: the boundary links (0, 4) touch exactly one rung,
    the interior links (1-3) touch two, and both are searched when they do --
    there is no "which side did you mean" signal in the reviewer's single
    link index, so this tries both rather than guessing.
    """
    if not 0 <= bad_link < CHAIN_LINKS:
        raise ValueError(f"bad_link must be 0..{CHAIN_LINKS - 1}, got {bad_link}")

    g = augmented(graph, manual_edges)
    nodes = puzzle.nodes
    last_rung = len(puzzle.solution) - 1
    slots = sorted({j for j in (bad_link - 1, bad_link) if 0 <= j <= last_rung})

    found: list[LinkFix] = []
    for idx in slots:
        old_word = nodes[idx + 1]
        left, right = nodes[idx], nodes[idx + 2]
        # Everything currently on screen, including `old_word` -- a candidate
        # equal to any of these (old_word itself included, which would be a
        # no-op "fix") is not a real suggestion.
        on_screen = frozenset({*nodes, *puzzle.bank})
        # For the stem/substring check only, `old_word` is excluded: it is
        # leaving the screen, so a candidate that merely rhymes with the word
        # it is replacing (not with anything staying) is not a conflict --
        # the same reasoning `swap_decoy` applies to `removed`.
        rest = on_screen - {old_word}

        pool = sorted(set(sorted_neighbours(g, left)) & set(sorted_neighbours(g, right)))
        scored: list[LinkFix] = []
        for candidate in pool:
            if candidate in on_screen:
                continue
            if shares_stem(stemmer, candidate, rest) or overlaps_substring(candidate, rest):
                continue

            trial_nodes = nodes[: idx + 1] + (candidate,) + nodes[idx + 2 :]
            if cfg.enforce_chordless and has_chord(g, trial_nodes):
                continue

            trial_bank = tuple(candidate if w == old_word else w for w in puzzle.bank)
            if not is_uniquely_solvable(g, puzzle.start, puzzle.end, trial_bank, cfg.chain_length):
                continue

            weight = g[left][candidate]["weight"] + g[candidate][right]["weight"]
            scored.append(LinkFix(index=idx, word=candidate, temptingness=weight, source="link-fix"))

        found.extend(scored)

    found.sort(key=lambda f: (-f.temptingness, f.index, f.word))
    return found[:limit]
