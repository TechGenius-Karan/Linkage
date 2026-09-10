"""Folding review rounds into `decisions.json` (planning.md 16.2).

Round 1 was judged before the admin existed and kept as data only, so without
this those 25 candidates come round the queue a second time.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from linkage_engine.cli import app
from linkage_engine.config import Config
from linkage_engine.data import exporters
from linkage_engine.domain import decisions as dec

runner = CliRunner()


def candidate(hash_: str) -> dict:
    return {
        "hash": hash_,
        "start": "whale",
        "end": "wings",
        "solution": ["ocean", "blue", "sky", "birds"],
        "bank": ["sea", "ocean", "cloud", "sky", "shark", "blue", "nest", "birds"],
        "quality": 0.8,
        "weights": [2.8, 4.4, 10.8, 6.6, 3.5],
        "relations": [["IsA"]] * 5,
    }


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A miniature repo, with the CLI pointed at it."""
    cfg = Config(repo_root=tmp_path)
    cfg.engine_dir.mkdir(parents=True, exist_ok=True)
    cfg.candidates_path.write_text(
        json.dumps([candidate("aaa"), candidate("bbb"), candidate("ccc")]), encoding="utf-8"
    )
    (cfg.engine_dir / "reviews").mkdir(parents=True, exist_ok=True)
    (cfg.engine_dir / "reviews" / "round-01.json").write_text(
        json.dumps(
            {
                "round": 1,
                "reviewed": "2026-09-05",
                "verdicts": [
                    {"hash": "aaa", "verdict": "approve"},
                    {"hash": "bbb", "verdict": "reject"},
                    {"hash": "zzz", "verdict": "approve"},  # not in candidates.json
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("linkage_engine.cli.Config", lambda: cfg)
    return cfg


def run(*args: str):
    result = runner.invoke(app, ["import-verdicts", *args])
    assert result.exit_code == 0, result.output
    return result


class TestDryRun:
    def test_writes_nothing(self, repo):
        # A --dry-run that writes is worse than no flag at all: it teaches the
        # reviewer to trust a promise the command does not keep.
        run("--dry-run")
        assert not repo.decisions_path.exists()

    def test_still_reports_what_it_would_do(self, repo):
        assert "Would import 2" in run("--dry-run").output


class TestImport:
    def test_approvals_land_undated(self, repo):
        # A verdict records taste; scheduling is separate. Importing a date
        # would recreate the coupling 7.7.3 exists to remove.
        run()
        stored = exporters.read_decisions(repo.decisions_path)["aaa"]
        assert stored.verdict == dec.ACCEPT
        assert stored.date is None
        assert stored.is_pooled

    def test_keeps_the_original_review_date(self, repo):
        run()
        assert exporters.read_decisions(repo.decisions_path)["aaa"].decided_at == "2026-09-05"

    def test_rejections_carry_a_reason_that_names_the_gap(self, repo):
        # Round 1 recorded no per-verdict reason and `reject()` requires one.
        # Inventing a plausible reason would poison the field this data exists
        # to fill, so the placeholder says what actually happened.
        run()
        stored = exporters.read_decisions(repo.decisions_path)["bbb"]
        assert stored.verdict == dec.REJECT
        assert "not recorded" in (stored.reason or "")
        assert stored.bad_link is None

    def test_skips_a_hash_the_candidate_pool_no_longer_has(self, repo):
        run()
        assert "zzz" not in exporters.read_decisions(repo.decisions_path)

    def test_reports_the_orphan_rather_than_swallowing_it(self, repo):
        assert "orphaned" in run().output

    def test_is_idempotent(self, repo):
        run()
        first = repo.decisions_path.read_text(encoding="utf-8")
        run()
        assert repo.decisions_path.read_text(encoding="utf-8") == first

    def test_never_overwrites_a_later_judgement(self, repo):
        """Re-running must not clobber a verdict made since the import."""
        run()
        decisions = exporters.read_decisions(repo.decisions_path)
        decisions["aaa"] = dec.reject("2026-09-11", reason="changed my mind")
        exporters.write_decisions(repo.decisions_path, decisions)

        run()
        assert exporters.read_decisions(repo.decisions_path)["aaa"].reason == "changed my mind"

    def test_leaves_undecided_candidates_in_the_queue(self, repo):
        run()
        assert "ccc" not in exporters.read_decisions(repo.decisions_path)


def test_no_review_files_is_not_an_error(tmp_path, monkeypatch):
    cfg = Config(repo_root=tmp_path)
    cfg.engine_dir.mkdir(parents=True, exist_ok=True)
    cfg.candidates_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr("linkage_engine.cli.Config", lambda: cfg)

    result = runner.invoke(app, ["import-verdicts"])
    assert result.exit_code == 0
    assert "No review files" in result.output
