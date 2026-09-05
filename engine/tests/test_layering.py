"""Enforce the dependency rule (planning.md 4.2).

    Dependencies point inward. The Domain tier imports nothing from
    Presentation or Data.

The plan promises an ESLint `no-restricted-imports` rule for the TypeScript
half. This is the Python equivalent, and it exists for the same reason: a
layering rule nobody can violate accidentally is worth more than one everyone
agrees to remember.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import linkage_engine

PACKAGE = Path(linkage_engine.__file__).parent
DOMAIN = PACKAGE / "domain"

#: Modules that mean "this code performs I/O". networkx is deliberately absent
#: -- it is an in-memory data structure, not an external boundary.
IO_MODULES = frozenset(
    {
        "requests",
        "urllib",
        "urllib.request",
        "socket",
        "http",
        "gzip",
        "pickle",
        "shutil",
        "tempfile",
        "sqlite3",
        "orjson",
        "wordfreq",
        "nltk",
        "typer",
        "tqdm",
        "click",
    }
)

#: `..config` is allowed: it is a frozen settings object with no behaviour
#: beyond hashing itself. Depending on configuration is not depending on an
#: implementation, and threading six primitives through every signature to
#: avoid it would be ceremony, not design.
ALLOWED_INTERNAL_PREFIXES = ("config",)


def _domain_modules() -> list[Path]:
    files = sorted(p for p in DOMAIN.glob("*.py"))
    assert files, f"no domain modules found under {DOMAIN}"
    return files


def _imports(path: Path) -> list[tuple[str, int]]:
    """Every imported module name in `path`, as (name, lineno).

    Relative imports are rendered with leading dots so `from ..data import x`
    surfaces as `..data`.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append(("." * node.level + (node.module or ""), node.lineno))
    return found


@pytest.mark.parametrize("module", _domain_modules(), ids=lambda p: p.name)
def test_domain_never_imports_the_data_or_cli_tiers(module: Path):
    for name, lineno in _imports(module):
        # Compare whole path segments. Substring matching would flag stdlib
        # `dataclasses` as the `data` tier, which is exactly the kind of
        # false positive that gets a layering rule switched off.
        root = name.lstrip(".").split(".")[0]
        assert root != "data", (
            f"{module.name}:{lineno} imports {name!r} -- the domain tier must "
            "not depend on data access (planning.md 4.2)"
        )
        assert root != "cli", (
            f"{module.name}:{lineno} imports {name!r} -- the domain tier must "
            "not depend on presentation (planning.md 4.2)"
        )


@pytest.mark.parametrize("module", _domain_modules(), ids=lambda p: p.name)
def test_domain_performs_no_io(module: Path):
    for name, lineno in _imports(module):
        root = name.lstrip(".").split(".")[0]
        assert root not in IO_MODULES, (
            f"{module.name}:{lineno} imports {name!r} -- the domain tier is "
            "pure: no I/O, no network, no filesystem (planning.md 4.2)"
        )


@pytest.mark.parametrize("module", _domain_modules(), ids=lambda p: p.name)
def test_domain_relative_imports_stay_inside_domain_or_config(module: Path):
    for name, lineno in _imports(module):
        if not name.startswith("."):
            continue
        target = name.lstrip(".")
        if target == "" or target.startswith(ALLOWED_INTERNAL_PREFIXES):
            continue
        # A single-dot import is a sibling inside domain/, which is fine.
        if not name.startswith(".."):
            continue
        pytest.fail(
            f"{module.name}:{lineno} reaches outside the domain tier via {name!r}"
        )


def test_the_data_tier_may_depend_on_domain_but_not_the_reverse():
    """Sanity check that the arrow really does point inward: at least one
    data module imports domain, and no domain module imports data."""
    data_files = sorted((PACKAGE / "data").glob("*.py"))
    assert data_files

    data_imports_domain = any(
        any(n.lstrip(".").split(".")[0] == "domain" for n, _ in _imports(p))
        for p in data_files
    )
    assert data_imports_domain, "expected the data tier to implement domain contracts"
