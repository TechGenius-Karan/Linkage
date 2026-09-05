"""All tunable constants in one place (planning.md Appendix A).

Changing generation behaviour should never mean hunting through source. Every
knob that affects the built graph lives here and is fingerprinted into the
graph's metadata, so a graph built under one config is detectably different
from one built under another.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from `start` until a directory containing `.git` is found.

    Falls back to the package's own grandparent so the tool still works when
    run from outside a checkout (e.g. an installed wheel in a scratch dir).
    """
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".git").exists():
            return candidate
    # src/linkage_engine/config.py -> linkage_engine -> src -> engine -> root
    return Path(__file__).resolve().parents[3]


# ConceptNet 5.7 assertions dump. Pinned by URL; verified by SHA-256 on every
# run after the first (see data/conceptnet.py for the trust-on-first-use note).
CONCEPTNET_VERSION = "5.7.0"
CONCEPTNET_URL = (
    "https://s3.amazonaws.com/conceptnet/downloads/2019/edges/"
    "conceptnet-assertions-5.7.0.csv.gz"
)


@dataclass(frozen=True, slots=True)
class Config:
    """Immutable generation config. Tests construct narrowed variants."""

    # --- Vocabulary (planning.md 7.1) ---
    # Two distinct constants on purpose: fetch_n is how many frequency-ranked
    # words wordfreq returns, target is how many survive the filter chain.
    # fetch_n is sized from a measured survival rate, not guessed: at 12,000
    # only ~7,440 words clear the filter chain, which leaves the target
    # unreachable. Roughly 65% survive, so 13,000 is what actually yields
    # 8,000. Re-measure if the filters change.
    vocab_fetch_n: int = 13_000
    vocab_target: int = 8_000
    vocab_min_rank: int = 500  # skip the too-generic head of the frequency list
    word_min_len: int = 3
    word_max_len: int = 12

    # --- Graph construction (planning.md 7.2) ---
    # Kept permissive here on purpose. 2.0 is the *path* gate applied in
    # Phase 2; building the graph at 1.0 keeps it rich enough for distractor
    # generation. See planning.md 7.9.4 Tier 1.
    min_graph_edge_weight: float = 1.0

    # --- Hub removal (planning.md 7.3) ---
    # DISABLED. Automatic degree pruning is off; `domain.wordlists.GENERIC_HUBS`
    # does this job by hand instead.
    #
    # Measured in Phase 1: at P99 the cutoff removed 75 words at degree > 82 --
    # animal, art, ball, bird, box, bridge. Those are good puzzle words. Degree
    # measures how *connected* a word is; the thing that ruins a puzzle is how
    # *generic* it is, and those are not the same property. `bird` is connected
    # to everything because birds genuinely relate to flight, eggs, song and
    # dinosaurs. `thing` is connected to everything because it means nothing.
    # A degree count cannot tell those apart. A person can.
    #
    # Set a float to re-enable pruning. The machinery is kept and tested, and
    # `build-graph` still *reports* the highest-degree words as candidates for
    # the curated list -- which is the useful half of this idea
    # (planning.md 7.9.4 Tier 3, Risk #19).
    hub_percentile: float | None = None

    #: Highest-degree words shown after a build, as blocklist candidates.
    hub_report_top_n: int = 40

    # --- Reproducibility (planning.md 7.8) ---
    seed: int = 20_261_001

    # --- Dataset ---
    conceptnet_version: str = CONCEPTNET_VERSION
    conceptnet_url: str = CONCEPTNET_URL
    # Optional pin. Left None for trust-on-first-use: the first download
    # records its hash to a sidecar file and every later run verifies against
    # it. Set this to hard-pin a known-good digest.
    conceptnet_sha256: str | None = None

    # --- Paths ---
    repo_root: Path = field(default_factory=find_repo_root)

    @property
    def data_dir(self) -> Path:
        return self.repo_root / "data"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def dump_path(self) -> Path:
        return self.raw_dir / f"conceptnet-assertions-{self.conceptnet_version}.csv.gz"

    @property
    def graph_path(self) -> Path:
        return self.data_dir / "linkage-graph.gpickle"

    def fingerprint(self) -> str:
        """Stable hash of every field that changes the built graph.

        Stamped into graph metadata so `generate` can refuse to run against a
        graph built under different settings (planning.md 7.8).
        """
        payload = {
            k: v
            for k, v in asdict(self).items()
            # repo_root is machine-specific and must not affect the fingerprint
            if k != "repo_root"
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


DEFAULT = Config()
