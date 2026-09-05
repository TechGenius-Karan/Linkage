"""Shared fixtures.

Everything here runs on committed fixtures. No test in this suite may require
the 1.2 GB ConceptNet dump or a network connection -- CI has neither
(planning.md 7.10, 11).
"""

from __future__ import annotations

import gzip
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

#: The words the sample fixture is written against.
SAMPLE_VOCAB = frozenset(
    {"apple", "newton", "gravity", "moon", "tide", "ocean", "pie", "orbit"}
)


@pytest.fixture(scope="session")
def sample_csv() -> Path:
    path = FIXTURES / "conceptnet-sample.csv"
    assert path.exists(), f"missing fixture: {path}"
    return path


@pytest.fixture(scope="session")
def sample_csv_gz(sample_csv: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Gzipped copy of the sample.

    The fixture is committed uncompressed so it stays reviewable in a diff;
    gzipping it here also exercises the real code path, since the actual dump
    is always `.gz`.
    """
    dest = tmp_path_factory.mktemp("conceptnet") / "sample.csv.gz"
    with sample_csv.open("rb") as src, gzip.open(dest, "wb") as out:
        shutil.copyfileobj(src, out)
    return dest


@pytest.fixture
def sample_vocab() -> frozenset[str]:
    return SAMPLE_VOCAB
