"""Fetch and stream-parse the ConceptNet assertions dump (planning.md 7.2).

Data tier: network and filesystem live here.

The dump is ~1.2 GB compressed and roughly 34 million assertions across all
languages. It is never loaded into memory whole -- `ConceptNetLoader` is a
streaming iterator, and the expensive JSON parse is deferred until a line has
already survived every cheap string test.
"""

from __future__ import annotations

import gzip
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, IO, Iterator

import orjson
import requests

from ..domain.models import Assertion

#: How often the optional progress callback fires, in lines read.
PROGRESS_EVERY = 500_000

_CHUNK = 1 << 20  # 1 MiB


# --------------------------------------------------------------------------
# Download + integrity
# --------------------------------------------------------------------------


def sha256_of(path: Path) -> str:
    """Streaming SHA-256 so a 1.2 GB file never lands in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _sidecar(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".sha256")


def download(
    url: str,
    dest: Path,
    *,
    expected_sha256: str | None = None,
    progress: Callable[[int, int | None], None] | None = None,
) -> str:
    """Download `url` to `dest` and return the file's SHA-256.

    Integrity policy is trust-on-first-use. ConceptNet does not publish a
    digest alongside the dump, so inventing a hardcoded one would be a lie.
    Instead the first successful download records its digest to a `.sha256`
    sidecar and every later run verifies against it; set
    `Config.conceptnet_sha256` to hard-pin a digest you have verified
    yourself.

    Writes to a `.part` file and renames on success, so an interrupted
    download can never be mistaken for a complete one.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".part")

    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        total_header = response.headers.get("Content-Length")
        total = int(total_header) if total_header else None
        written = 0
        with partial.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=_CHUNK):
                if not chunk:
                    continue
                fh.write(chunk)
                written += len(chunk)
                if progress:
                    progress(written, total)

    digest = sha256_of(partial)
    if expected_sha256 and digest != expected_sha256:
        partial.unlink(missing_ok=True)
        raise ValueError(
            f"SHA-256 mismatch for {url}\n"
            f"  expected {expected_sha256}\n"
            f"  got      {digest}\n"
            "Refusing to use this file."
        )

    partial.replace(dest)
    _sidecar(dest).write_text(digest, encoding="utf-8")
    return digest


def verify_cached(path: Path, expected_sha256: str | None = None) -> str:
    """Re-verify an already-downloaded dump. Returns its digest.

    Checks against the explicit pin if there is one, otherwise against the
    sidecar written at download time.
    """
    digest = sha256_of(path)
    pin = expected_sha256 or (
        _sidecar(path).read_text(encoding="utf-8").strip()
        if _sidecar(path).exists()
        else None
    )
    if pin and digest != pin:
        raise ValueError(
            f"SHA-256 mismatch for cached {path.name}\n"
            f"  expected {pin}\n"
            f"  got      {digest}\n"
            "The cached dump is corrupt or was replaced. Delete it and re-download."
        )
    if not pin:
        _sidecar(path).write_text(digest, encoding="utf-8")
    return digest


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def parse_concept(uri: str) -> str | None:
    """`/c/en/apple/n/wn/food` -> `apple`. Returns None if unusable.

    Rejects non-English concepts and multiword lemmas (ConceptNet writes those
    as `/c/en/ice_cream`); long tiles break the mobile layout and read as
    phrases rather than concepts (planning.md 3.1.1).
    """
    if not uri.startswith("/c/en/"):
        return None
    rest = uri[6:]
    slash = rest.find("/")
    lemma = rest if slash == -1 else rest[:slash]
    if not lemma or "_" in lemma:
        return None
    return lemma


@dataclass(slots=True)
class ParseCounters:
    """Where every line of the dump went. Read after iteration completes."""

    lines: int = 0
    malformed: int = 0
    rejected_relation: int = 0
    rejected_concept: int = 0
    rejected_filter: int = 0
    kept: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "lines": self.lines,
            "malformed": self.malformed,
            "rejected_relation": self.rejected_relation,
            "rejected_concept": self.rejected_concept,
            "rejected_filter": self.rejected_filter,
            "kept": self.kept,
        }


def _open_text(path: Path) -> IO[str]:
    """Open plain or gzipped CSV. Both, so a decompressed slice of the dump
    (`zcat ... | head -100000`) can be used for debugging without ceremony."""
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("rt", encoding="utf-8", errors="replace")


@dataclass(slots=True)
class ConceptNetLoader:
    """Streams `Assertion`s out of the dump.

    Single Responsibility: this class parses. It does not decide *what* is
    worth keeping -- `relation_filter` and `concept_filter` are injected, so
    the parser has no opinion about relation policy or vocabulary and can be
    tested against either.
    """

    path: Path
    relation_filter: Callable[[str], bool]
    concept_filter: Callable[[str], bool]
    progress: Callable[[int], None] | None = None
    #: Stop after this many lines. For smoke-testing the pipeline against the
    #: real dump in seconds rather than the full ~20 minute parse.
    max_lines: int | None = None
    counters: ParseCounters = field(default_factory=ParseCounters)

    def __iter__(self) -> Iterator[Assertion]:
        c = self.counters
        keep_relation = self.relation_filter
        keep_concept = self.concept_filter
        limit = self.max_lines

        with _open_text(self.path) as fh:
            for line in fh:
                if limit is not None and c.lines >= limit:
                    break
                c.lines += 1
                if self.progress and c.lines % PROGRESS_EVERY == 0:
                    self.progress(c.lines)

                fields = line.rstrip("\n").split("\t")
                if len(fields) < 5:
                    c.malformed += 1
                    continue

                # Cheapest tests first. Roughly 95% of lines die here, which is
                # what keeps the expensive JSON parse below off the hot path.
                if not keep_relation(fields[1]):
                    c.rejected_relation += 1
                    continue

                start = parse_concept(fields[2])
                if start is None:
                    c.rejected_concept += 1
                    continue
                end = parse_concept(fields[3])
                if end is None:
                    c.rejected_concept += 1
                    continue

                if not keep_concept(start) or not keep_concept(end):
                    c.rejected_filter += 1
                    continue

                try:
                    weight = float(orjson.loads(fields[4]).get("weight", 1.0))
                except (orjson.JSONDecodeError, ValueError, TypeError, AttributeError):
                    c.malformed += 1
                    continue

                c.kept += 1
                yield Assertion(
                    start=start,
                    end=end,
                    relation=fields[1][3:] if fields[1].startswith("/r/") else fields[1],
                    weight=weight,
                )
