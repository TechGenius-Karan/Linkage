"""Presentation tier: the `linkage` command line (planning.md 4.1).

This module formats input and output. Every decision it reports was made by
the domain tier; every byte it reads or writes went through the data tier.
"""

from __future__ import annotations

import random
import statistics
from pathlib import Path
from typing import Annotated

import networkx as nx
import typer
from tqdm import tqdm

from . import __version__, review as review_ui
from .config import DEFAULT, Config
from .data import codec, conceptnet, exporters, graph_store
from .data.pos import make_pos_checker
from .data.stemming import PorterStemmerAdapter
from .data.vocabulary import build_vocabulary
from .domain import corpus, graph_builder, hubs
from .domain.distractors import DistractorSelector
from .domain.generator import CandidateGenerator
from .domain.models import Candidate, Path as ChainPath
from .domain.relations import ALLOWLIST, is_allowed
from .domain.scoring import QualityScorer


def _load_graph(cfg: Config) -> nx.Graph:
    """Load the graph and warn if it predates the current config."""
    graph = graph_store.load(cfg.graph_path)
    warning = graph_store.check_fingerprint(graph, cfg)
    if warning:
        typer.secho(f"WARNING: {warning}", fg=typer.colors.YELLOW)
    return graph


def _candidate_from_dict(row: dict) -> Candidate:
    """Rehydrate a candidate from candidates.json for export."""
    path = ChainPath(
        start=row["start"],
        end=row["end"],
        steps=tuple(row["solution"]),
        weights=tuple(row["weights"]),
        relations=tuple(tuple(r) for r in row["relations"]),
    )
    return Candidate(
        path=path,
        bank=tuple(row["bank"]),
        quality=row["quality"],
        score_breakdown=tuple(sorted(row.get("scores", {}).items())),
    )

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Offline puzzle generation for the Linkage daily word game.",
)


def _echo_header(text: str) -> None:
    typer.secho(f"\n{text}", fg=typer.colors.CYAN, bold=True)


def _ensure_dump(cfg: Config, dump: Path | None) -> tuple[Path, str]:
    """Resolve the dump path, downloading if needed. Returns (path, sha256)."""
    path = dump or cfg.dump_path

    if path.exists():
        size_mb = path.stat().st_size / (1024 * 1024)
        typer.echo(f"  using cached dump  {path}  ({size_mb:,.0f} MB)")
        if size_mb > 100:
            typer.echo("  verifying SHA-256 (reads the whole file, ~30s)...")
        return path, conceptnet.verify_cached(path, cfg.conceptnet_sha256)

    if dump is not None:
        raise typer.BadParameter(f"No such dump: {dump}")

    typer.echo(f"  downloading  {cfg.conceptnet_url}")
    typer.echo("  ~1.2 GB, this takes a while on first run")
    bar = tqdm(unit="B", unit_scale=True, unit_divisor=1024, desc="  download")

    def on_progress(written: int, total: int | None) -> None:
        if total and bar.total is None:
            bar.total = total
        bar.update(written - bar.n)

    try:
        digest = conceptnet.download(
            cfg.conceptnet_url,
            path,
            expected_sha256=cfg.conceptnet_sha256,
            progress=on_progress,
        )
    finally:
        bar.close()

    if cfg.conceptnet_sha256 is None:
        typer.secho(
            f"  recorded SHA-256 {digest} (trust-on-first-use; later runs verify it)",
            fg=typer.colors.YELLOW,
        )
    return path, digest


@app.command("build-graph")
def build_graph(
    force: Annotated[
        bool, typer.Option("--force", help="Rebuild even if a graph already exists.")
    ] = False,
    no_pos_filter: Annotated[
        bool,
        typer.Option(
            "--no-pos-filter",
            help="Skip the WordNet noun restriction. Faster, but chains are "
            "noticeably less coherent.",
        ),
    ] = False,
    dump: Annotated[
        Path | None,
        typer.Option("--dump", help="Use a local dump instead of downloading."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            help="Parse only the first N lines. Smoke-tests the pipeline in "
            "seconds instead of ~20 minutes.",
        ),
    ] = None,
) -> None:
    """Download ConceptNet, build the concept graph, and save it to disk."""
    cfg = DEFAULT

    if cfg.graph_path.exists() and not force:
        typer.secho(
            f"Graph already exists at {cfg.graph_path}\nUse --force to rebuild.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(0)

    _echo_header("1/5  Dataset")
    dump_path, digest = _ensure_dump(cfg, dump)
    typer.echo(f"  sha256  {digest}")

    _echo_header("2/5  Vocabulary")
    pos = make_pos_checker(enabled=not no_pos_filter)
    if no_pos_filter:
        typer.secho("  POS filter DISABLED (--no-pos-filter)", fg=typer.colors.YELLOW)
    vocab = build_vocabulary(cfg, pos)
    typer.echo(f"  considered  {vocab.considered:,}  (ranks {cfg.vocab_min_rank}+)")
    typer.echo(f"  kept        {vocab.kept:,}")
    for name, count in sorted(vocab.rejected_by.items(), key=lambda kv: -kv[1]):
        if count:
            typer.echo(f"    rejected {name:<16} {count:>7,}")

    if vocab.kept < 1000:
        typer.secho(
            f"  WARNING: only {vocab.kept} words survived. Expected ~{cfg.vocab_target}.",
            fg=typer.colors.RED,
        )

    _echo_header("3/5  Parsing assertions")
    typer.echo(f"  relations allowed: {len(ALLOWLIST)}  ({', '.join(sorted(ALLOWLIST))})")
    bar = tqdm(unit=" lines", unit_scale=True, desc="  parse", total=limit)
    loader = conceptnet.ConceptNetLoader(
        path=dump_path,
        relation_filter=is_allowed,
        concept_filter=vocab.words.__contains__,
        progress=lambda n: bar.update(n - bar.n),
        max_lines=limit,
    )

    _echo_header("4/5  Building graph")
    try:
        graph = graph_builder.build(loader, vocab.words, cfg.min_graph_edge_weight)
    finally:
        bar.update(loader.counters.lines - bar.n)
        bar.close()

    for key, value in loader.counters.as_dict().items():
        typer.echo(f"  {key:<20} {value:>12,}")

    if graph.number_of_nodes() == 0:
        typer.secho(
            "\nGraph is empty. Nothing survived the filters -- check the dump "
            "and the vocabulary above.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    typer.echo(f"  before pruning       {graph.number_of_nodes():>12,} nodes")
    typer.echo(f"                       {graph.number_of_edges():>12,} edges")

    if cfg.hub_percentile is None:
        removed_hubs, cutoff = set(), 0
        typer.echo(
            "  hub pruning          disabled -- curated GENERIC_HUBS list only"
        )
    else:
        removed_hubs, cutoff = graph_builder.prune_hubs(graph, cfg.hub_percentile)
        typer.echo(
            f"  hub cutoff (P{cfg.hub_percentile:g})     degree > {cutoff}"
            f"  -> removed {len(removed_hubs):,}"
        )
        if removed_hubs:
            typer.echo(f"    e.g. {', '.join(sorted(removed_hubs)[:12])}")

    orphans = graph_builder.drop_isolated(graph)
    stats = graph_builder.summarise(
        graph,
        hubs_removed=len(removed_hubs),
        isolated_removed=len(orphans),
        hub_degree_cutoff=cutoff,
    )
    typer.echo(f"  isolated removed     {len(orphans):>12,}")

    _echo_header("5/5  Saving")
    meta = graph_store.build_meta(
        cfg,
        conceptnet_sha256=digest,
        vocab_size=vocab.kept,
        extra={
            "hub_degree_cutoff": cutoff,
            "hubs_removed": len(removed_hubs),
            "pos_filter": not no_pos_filter,
            "partial_parse_limit": limit,
        },
    )
    graph_store.save(graph, cfg.graph_path, meta)

    size_mb = cfg.graph_path.stat().st_size / (1024 * 1024)
    typer.echo(f"  {cfg.graph_path}  ({size_mb:.1f} MB)")

    _echo_header("Blocklist candidates")
    typer.echo(
        "  Highest-degree words. Anything here that is generic rather than\n"
        "  merely well-connected belongs in domain/wordlists.py GENERIC_HUBS."
    )
    for name, degree in hubs.top_by_degree(graph, cfg.hub_report_top_n):
        typer.echo(f"    {degree:>4}  {name}")

    _echo_header("Result")
    typer.echo(f"  nodes          {stats.nodes:>12,}")
    typer.echo(f"  edges          {stats.edges:>12,}")
    typer.echo(f"  mean degree    {stats.mean_degree:>12}")
    typer.echo(f"  median degree  {stats.median_degree:>12}")
    typer.echo(f"  max degree     {stats.max_degree:>12}")
    typer.secho("\nNext:  linkage inspect apple", fg=typer.colors.GREEN)


@app.command()
def inspect(
    word: Annotated[str, typer.Argument(help="Word to look up.")],
    top: Annotated[int, typer.Option("--top", help="Neighbours to show.")] = 25,
) -> None:
    """Spot-check a word's neighbours -- the Phase 1 verification step.

    Neighbours should read like human association, not noise. If they do not,
    the filters in planning.md 7.1-7.3 need tuning before Phase 2.
    """
    cfg = DEFAULT
    graph = graph_store.load(cfg.graph_path)

    warning = graph_store.check_fingerprint(graph, cfg)
    if warning:
        typer.secho(f"WARNING: {warning}", fg=typer.colors.YELLOW)

    node = word.strip().lower()
    if node not in graph:
        typer.secho(f"'{node}' is not in the graph.", fg=typer.colors.RED)
        raise typer.Exit(1)

    ranked = hubs.sorted_neighbours(graph, node, limit=top)
    typer.secho(f"\n{node}  (degree {graph.degree(node)})", bold=True)
    for name in ranked:
        edge = graph[node][name]
        rels = ", ".join(edge.get("relations", ()))
        typer.echo(f"  {edge['weight']:>6.2f}  {name:<18} {rels}")


@app.command()
def stats() -> None:
    """Summarise the built graph and its provenance."""
    cfg = DEFAULT
    graph = graph_store.load(cfg.graph_path)

    warning = graph_store.check_fingerprint(graph, cfg)
    if warning:
        typer.secho(f"WARNING: {warning}", fg=typer.colors.YELLOW)

    _echo_header("Provenance")
    for key in sorted(graph.graph):
        typer.echo(f"  {key:<24} {graph.graph[key]}")

    degrees = [d for _, d in graph.degree()]
    _echo_header("Shape")
    typer.echo(f"  nodes  {graph.number_of_nodes():,}")
    typer.echo(f"  edges  {graph.number_of_edges():,}")

    _echo_header("Degree distribution")
    for bucket, count in hubs.degree_histogram(degrees).items():
        typer.echo(f"  {bucket:>8}  {count:>7,}")


@app.command()
def diagnose(
    samples: Annotated[
        int, typer.Option("--samples", help="Endpoint pairs to sample.")
    ] = 200,
) -> None:
    """Graph shape and the survival funnel (planning.md 7.9.3).

    Run this BEFORE generating. It converts the yield question from "unknown,
    possibly fatal" into a table you read off the screen, and it tells you
    which constraint is actually costing you -- not the one you guessed.
    """
    cfg = DEFAULT
    graph = _load_graph(cfg)
    degrees = [d for _, d in graph.degree()]

    _echo_header("Graph shape")
    typer.echo(f"  nodes                 {graph.number_of_nodes():>12,}")
    typer.echo(f"  edges                 {graph.number_of_edges():>12,}")
    components = sorted(nx.connected_components(graph), key=len, reverse=True)
    largest = len(components[0]) if components else 0
    typer.echo(
        f"  components            {len(components):>12,}   "
        f"largest {largest:,} ({100 * largest / max(1, graph.number_of_nodes()):.1f}%)"
    )
    typer.echo(f"  mean degree           {statistics.fmean(degrees):>12.2f}")
    typer.echo(f"  median degree         {int(statistics.median(degrees)):>12,}")
    typer.echo(f"  max degree            {max(degrees):>12,}")

    # The single number that predicts the chordless kill rate.
    typer.echo(f"  avg clustering        {nx.average_clustering(graph):>12.4f}")
    typer.echo(f"  transitivity          {nx.transitivity(graph):>12.4f}")

    _echo_header("Edge weight distribution")
    weights = [d["weight"] for _, _, d in graph.edges(data=True)]
    for threshold in (1.5, 2.0, 2.5, 3.0, 5.0):
        p = sum(w >= threshold for w in weights) / len(weights)
        marker = "  <-- MIN_EDGE_WEIGHT" if threshold == cfg.min_edge_weight else ""
        typer.echo(f"  >= {threshold:<4} {p * 100:>6.1f}%   p^5 = {p**5 * 100:>8.4f}%{marker}")

    _echo_header(f"Survival funnel  ({samples} endpoint pairs)")
    rng = random.Random(cfg.seed)
    selector = DistractorSelector(cfg, PorterStemmerAdapter())
    generator = CandidateGenerator(graph, cfg, rng, selector, QualityScorer())

    bar = tqdm(total=samples, unit=" pairs", desc="  sampling")
    usable = 0
    for _ in generator.generate(wanted=samples, max_pairs=samples):
        usable += 1
    bar.update(generator.counts.pairs_sampled - bar.n)
    bar.close()

    counts = generator.counts
    typer.echo(f"  {'pairs sampled':<28} {counts.pairs_sampled:>12,}")
    previous = None
    for label, value in counts.as_rows():
        share = f"  ({100 * value / previous:5.1f}% of prev)" if previous else ""
        typer.echo(f"  {label:<28} {value:>12,}{share}")
        previous = value

    # Outside the funnel on purpose: several banks may be built for one pair,
    # but only the best-scoring becomes a candidate (one puzzle per pair,
    # planning.md 7.7.1).
    typer.echo(f"\n  {'safe banks built':<28} {counts.unique_bank:>12,}")
    typer.echo(f"  {'candidates emitted':<28} {usable:>12,}")

    per_thousand = 1000 * usable / max(1, counts.pairs_sampled)
    hit_rate = 100 * usable / max(1, counts.pairs_sampled)
    typer.echo(f"\n  usable candidates per 1k pairs   {per_thousand:,.0f}   ({hit_rate:.0f}% of pairs)")

    _echo_header("Go / no-go")
    if per_thousand < 3:
        typer.secho(
            "  BELOW THRESHOLD (3 per 1k). Climb the planning.md 7.9.4 remedy\n"
            "  ladder before writing more generator code.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    typer.secho(
        f"  PASS -- {per_thousand:,.0f} per 1k against a threshold of 3.",
        fg=typer.colors.GREEN,
    )


@app.command()
def generate(
    count: Annotated[
        int, typer.Option("--count", help="Candidates to generate this run.")
    ] = 800,
    until_approved: Annotated[
        int | None,
        typer.Option(
            "--until-approved",
            help="Top up until this many candidates are approved overall. "
            "Skips anything already decided.",
        ),
    ] = None,
    max_pairs: Annotated[
        int | None,
        typer.Option("--max-pairs", help="Endpoint pairs to try. Default: 40x count."),
    ] = None,
    seed_offset: Annotated[
        int, typer.Option("--seed-offset", help="Vary this to find different puzzles.")
    ] = 0,
) -> None:
    """Generate ranked, uniquely-solvable candidates for review."""
    cfg = DEFAULT
    graph = _load_graph(cfg)

    decisions = exporters.read_decisions(cfg.decisions_path)
    approved_now = sum(1 for v in decisions.values() if v == review_ui.ACCEPT)

    if until_approved is not None:
        shortfall = until_approved - approved_now
        if shortfall <= 0:
            typer.secho(
                f"Already {approved_now} approved (target {until_approved}). Nothing to do.",
                fg=typer.colors.GREEN,
            )
            raise typer.Exit(0)
        # Pessimistic acceptance rate so one run usually suffices.
        count = max(count, shortfall * 3)
        typer.echo(
            f"  {approved_now} approved, need {shortfall} more -> generating {count}"
        )
        typer.secho(
            "\n  NOTE: approving N candidates does not yield N puzzles.\n"
            "  `export` then thins the set again to keep words from repeating\n"
            f"  across the year. Measured at MAX_WORD_REUSE={cfg.max_word_reuse}:\n"
            "  roughly 15% of candidates survive diversity selection, so a full\n"
            "  year needs on the order of 2,500 approved. Raising the cap is the\n"
            "  lever if that is too much review (planning.md 7.7.1).",
            fg=typer.colors.YELLOW,
        )

    budget = max_pairs if max_pairs is not None else count * 40
    rng = random.Random(cfg.seed + seed_offset)
    selector = DistractorSelector(cfg, PorterStemmerAdapter())
    generator = CandidateGenerator(graph, cfg, rng, selector, QualityScorer())

    _echo_header(f"Generating up to {count:,} candidates (budget {budget:,} pairs)")
    existing = {row["hash"]: row for row in _safe_read_candidates(cfg)}
    typer.echo(f"  {len(existing):,} candidate(s) already on disk")

    bar = tqdm(total=count, unit=" cand", desc="  generating")
    fresh = 0
    for candidate in generator.generate(wanted=count, max_pairs=budget):
        digest = candidate.content_hash()
        if digest in decisions or digest in existing:
            continue
        existing[digest] = exporters.candidate_to_dict(candidate)
        fresh += 1
        bar.update(1)
    bar.close()

    rows = list(existing.values())
    exporters.write_candidate_rows(cfg.candidates_path, rows)

    counts = generator.counts
    _echo_header("Result")
    typer.echo(f"  pairs sampled     {counts.pairs_sampled:>10,}")
    typer.echo(f"  paths considered  {counts.paths_found:>10,}")
    typer.echo(f"  safe banks built  {counts.unique_bank:>10,}")
    typer.echo(f"  new candidates    {fresh:>10,}")
    typer.echo(f"  total on disk     {len(rows):>10,}")
    if rows:
        qualities = [r["quality"] for r in rows]
        typer.echo(
            f"  quality  best {max(qualities):.2f}  "
            f"median {statistics.median(qualities):.2f}  worst {min(qualities):.2f}"
        )
    typer.secho(f"\n  {cfg.candidates_path}", fg=typer.colors.BRIGHT_BLACK)
    typer.secho("\nNext:  linkage review", fg=typer.colors.GREEN)


def _safe_read_candidates(cfg: Config) -> list[dict]:
    try:
        return exporters.read_candidates(cfg.candidates_path)
    except FileNotFoundError:
        return []


@app.command()
def review(
    limit: Annotated[
        int | None, typer.Option("--limit", help="Stop after this many decisions.")
    ] = None,
    redo: Annotated[
        bool, typer.Option("--redo", help="Re-review candidates already decided.")
    ] = False,
) -> None:
    """Accept or reject candidates by hand (planning.md 7.7).

    Decisions are keyed by content hash and stored separately from
    candidates.json, so re-running `generate` never discards a judgement.
    """
    cfg = DEFAULT
    rows = exporters.read_candidates(cfg.candidates_path)
    decisions = exporters.read_decisions(cfg.decisions_path)

    queue = [r for r in rows if redo or r["hash"] not in decisions]
    if not queue:
        approved = sum(1 for v in decisions.values() if v == review_ui.ACCEPT)
        typer.secho(
            f"Nothing left to review. {approved} approved of {len(rows)} candidates.",
            fg=typer.colors.GREEN,
        )
        raise typer.Exit(0)

    typer.echo(f"\n{len(queue):,} candidate(s) to review. Ctrl-C or 'q' saves and exits.")
    decided = 0
    try:
        for index, row in enumerate(queue, start=1):
            if limit is not None and decided >= limit:
                break
            approved = sum(1 for v in decisions.values() if v == review_ui.ACCEPT)
            review_ui.render(row, index, len(queue), approved)
            verdict = review_ui.prompt()
            if verdict == "quit":
                break
            if verdict != review_ui.SKIP:
                decisions[row["hash"]] = verdict
                decided += 1
    except KeyboardInterrupt:
        typer.echo("\n  interrupted")
    finally:
        exporters.write_decisions(cfg.decisions_path, decisions)

    approved = sum(1 for v in decisions.values() if v == review_ui.ACCEPT)
    rejected = sum(1 for v in decisions.values() if v == review_ui.REJECT)
    _echo_header("Session")
    typer.echo(f"  decided this run  {decided:>6,}")
    typer.echo(f"  approved total    {approved:>6,}  / target {cfg.target_approved}")
    typer.echo(f"  rejected total    {rejected:>6,}")
    if approved >= cfg.target_approved:
        typer.secho(
            f"\nTarget reached. Next:  linkage export --start-date {cfg.epoch_date}",
            fg=typer.colors.GREEN,
        )


@app.command()
def export(
    start_date: Annotated[
        str, typer.Option("--start-date", help="Date of puzzle #1 (ISO).")
    ] = "",
    limit: Annotated[
        int | None, typer.Option("--limit", help="Ship at most this many puzzles.")
    ] = None,
    allow_short: Annotated[
        bool,
        typer.Option("--allow-short", help="Export even with fewer than the target."),
    ] = False,
) -> None:
    """Assemble the archive: per-day files, manifest, verification subgraph."""
    cfg = DEFAULT
    epoch = start_date or cfg.epoch_date
    graph = _load_graph(cfg)

    rows = {r["hash"]: r for r in exporters.read_candidates(cfg.candidates_path)}
    decisions = exporters.read_decisions(cfg.decisions_path)
    approved = [
        _candidate_from_dict(rows[h])
        for h, verdict in sorted(decisions.items())
        if verdict == review_ui.ACCEPT and h in rows
    ]

    if not approved:
        typer.secho("Nothing approved yet. Run `linkage review`.", fg=typer.colors.RED)
        raise typer.Exit(1)
    if len(approved) < cfg.target_approved and not allow_short:
        typer.secho(
            f"Only {len(approved)} approved, target is {cfg.target_approved}.\n"
            "Generate and review more, or pass --allow-short.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    approved.sort(key=lambda c: (-c.quality, c.content_hash()))

    # Enforce the corpus rules while choosing, rather than assembling a year
    # and rejecting it (planning.md 7.7.1). Same pattern as the bank builder.
    _echo_header("Diversity selection")
    target = limit or cfg.target_approved
    selected, selection = corpus.select_diverse(
        approved, target=target, max_word_reuse=cfg.max_word_reuse
    )
    typer.echo(f"  {selection.summary()}")
    if selection.selected < target:
        typer.secho(
            f"  Only {selection.selected} of {target} could be filled without "
            f"breaking the reuse cap.\n"
            f"  Approve more candidates, or raise MAX_WORD_REUSE.",
            fg=typer.colors.YELLOW,
        )
        if not allow_short:
            raise typer.Exit(1)

    # Launch week is the best of what survived selection; the rest is shuffled
    # so difficulty does not trend across the year (7.7.1).
    launch = selected[: cfg.launch_week_size]
    rest = selected[cfg.launch_week_size :]
    random.Random(cfg.seed).shuffle(rest)

    puzzles = exporters.assign_dates(launch + rest, epoch)

    _echo_header("Corpus quality control")
    try:
        report = corpus.check(puzzles, cfg.max_word_reuse)
    except corpus.CorpusViolation as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(1) from exc
    typer.secho(f"  PASS -- {report.summary()}", fg=typer.colors.GREEN)
    typer.echo(
        "  most reused: "
        + ", ".join(f"{w} x{n}" for w, n in report.most_reused[:6])
    )

    _echo_header("Writing archive")
    written = exporters.write_puzzles(cfg, puzzles)
    manifest = exporters.write_manifest(cfg, puzzles)
    licence = exporters.write_licence_notice(cfg)
    subgraph = exporters.write_verification_subgraph(cfg, graph, puzzles)
    codec_fixture = codec.write_fixture(cfg.codec_fixture_path)

    typer.echo(f"  {len(written):,} per-day files -> {cfg.puzzles_dir}")
    typer.echo(f"  {manifest.name}")
    typer.echo(f"  {licence.name}")
    typer.echo(
        f"  {subgraph.relative_to(cfg.repo_root)}  "
        f"({subgraph.stat().st_size / 1024:.0f} KB, NOT served)"
    )
    typer.echo(f"  {cfg.codec_fixture_path.name}  (key {codec_fixture['key']})")

    _echo_header("Result")
    typer.echo(f"  puzzles   {len(puzzles):,}")
    typer.echo(f"  #{puzzles[0].id} {puzzles[0].date}  ->  #{puzzles[-1].id} {puzzles[-1].date}")
    typer.secho("\nNext:  pytest", fg=typer.colors.GREEN)


@app.command()
def version() -> None:
    """Print the engine version."""
    typer.echo(__version__)
