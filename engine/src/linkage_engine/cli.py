"""Presentation tier: the `linkage` command line (planning.md 4.1).

This module formats input and output. Every decision it reports was made by
the domain tier; every byte it reads or writes went through the data tier.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from tqdm import tqdm

from . import __version__
from .config import DEFAULT, Config
from .data import conceptnet, graph_store
from .data.pos import make_pos_checker
from .data.vocabulary import build_vocabulary
from .domain import graph_builder, hubs
from .domain.relations import ALLOWLIST, is_allowed

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

    removed_hubs, cutoff = graph_builder.prune_hubs(graph, cfg.hub_percentile)
    orphans = graph_builder.drop_isolated(graph)
    stats = graph_builder.summarise(
        graph,
        hubs_removed=len(removed_hubs),
        isolated_removed=len(orphans),
        hub_degree_cutoff=cutoff,
    )

    typer.echo(
        f"  hub cutoff (P{cfg.hub_percentile:g})     degree > {cutoff}"
        f"  -> removed {len(removed_hubs):,}"
    )
    if removed_hubs:
        sample = ", ".join(sorted(removed_hubs)[:12])
        typer.echo(f"    e.g. {sample}")
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
def version() -> None:
    """Print the engine version."""
    typer.echo(__version__)
