"""Persist and reload the concept graph (planning.md 7.2).

Data tier: filesystem only.

    NetworkX 3.x gotcha: `nx.write_gpickle` / `nx.read_gpickle` were REMOVED
    in NetworkX 3.0. We pickle directly. The `.gpickle` extension is kept for
    continuity with the plan and with anyone's muscle memory.

Provenance is stamped into `graph.graph` so a graph built from a different
dataset, a different wordfreq release, or a different config is *detectable*
rather than silently reused (planning.md 7.8).
"""

from __future__ import annotations

import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx

from ..config import Config

#: Bumped when the stamped metadata shape changes.
META_VERSION = 1

PICKLE_PROTOCOL = 5


def build_meta(
    cfg: Config,
    *,
    conceptnet_sha256: str,
    vocab_size: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Everything needed to decide whether a cached graph is still valid."""
    from importlib.metadata import version

    from .. import __version__

    meta: dict[str, Any] = {
        "meta_version": META_VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config_fingerprint": cfg.fingerprint(),
        "conceptnet_version": cfg.conceptnet_version,
        "conceptnet_sha256": conceptnet_sha256,
        # wordfreq exposes no __version__ attribute; ask the installed
        # distribution instead. This is the reproducibility linchpin --
        # wordfreq's bundled frequency data changes between releases
        # (planning.md 7.1), so the built graph must record which one it saw.
        "wordfreq_version": version("wordfreq"),
        "networkx_version": nx.__version__,
        "linkage_engine_version": __version__,
        "vocab_size": vocab_size,
    }
    if extra:
        meta.update(extra)
    return meta


def save(graph: nx.Graph, path: Path, meta: dict[str, Any]) -> None:
    """Stamp metadata and pickle atomically.

    Writes to `.part` and renames, so an interrupted save can never leave a
    truncated pickle that looks loadable.
    """
    graph.graph.update(meta)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    with partial.open("wb") as fh:
        pickle.dump(graph, fh, protocol=PICKLE_PROTOCOL)
    partial.replace(path)


def load(path: Path) -> nx.Graph:
    """Load a graph. Raises FileNotFoundError with an actionable message."""
    if not path.exists():
        raise FileNotFoundError(
            f"No graph at {path}\nBuild one first:\n    linkage build-graph"
        )
    with path.open("rb") as fh:
        graph = pickle.load(fh)
    if not isinstance(graph, nx.Graph):
        raise TypeError(f"{path} does not contain a networkx Graph")
    return graph


def check_fingerprint(graph: nx.Graph, cfg: Config) -> str | None:
    """Return a warning string when the graph predates the current config.

    Phase 2's `generate` refuses to run on a mismatch. Phase 1 only warns --
    during development the config changes constantly and a hard failure would
    be noise.
    """
    stamped = graph.graph.get("config_fingerprint")
    current = cfg.fingerprint()
    if stamped is None:
        return "graph has no config fingerprint (built by an older version?)"
    if stamped != current:
        return (
            f"graph was built under config {stamped}, current config is "
            f"{current}. Rebuild with `linkage build-graph --force`."
        )
    return None
