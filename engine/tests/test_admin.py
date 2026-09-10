"""The admin's handlers (planning.md 16.3).

No HTTP here: the handlers are plain functions taking a Config, which is the
reason `server.py` holds the socket and nothing else.
"""

from __future__ import annotations

import json

import pytest

from linkage_engine.admin import handlers
from linkage_engine.config import Config
from linkage_engine.data import exporters
from linkage_engine.domain import decisions as dec


def candidate_row(hash_: str, quality: float = 0.8) -> dict:
    return {
        "hash": hash_,
        "start": "whale",
        "end": "wings",
        "solution": ["ocean", "blue", "sky", "birds"],
        "bank": ["sea", "ocean", "cloud", "sky", "shark", "blue", "nest", "birds"],
        "quality": quality,
        "weights": [2.8, 4.4, 10.8, 6.6, 3.5],
        "relations": [["AtLocation"], ["IsA"], ["RelatedTo"], ["IsA"], ["HasA"]],
    }


@pytest.fixture
def cfg(tmp_path):
    config = Config(repo_root=tmp_path)
    config.candidates_path.parent.mkdir(parents=True, exist_ok=True)
    config.candidates_path.write_text(
        json.dumps([candidate_row("aaa", 0.9), candidate_row("bbb", 0.5), candidate_row("ccc", 0.7)]),
        encoding="utf-8",
    )
    return config


class TestQueue:
    def test_returns_everything_undecided(self, cfg):
        assert len(handlers.queue(cfg)["puzzles"]) == 3

    def test_orders_by_quality_then_hash(self, cfg):
        # Stable ordering matters more than good ordering here: a reviewer who
        # reloads must not lose their place (7.7.2 is candid that the score
        # barely beats chance).
        order = [p["hash"] for p in handlers.queue(cfg)["puzzles"]]
        assert order == ["aaa", "ccc", "bbb"]
        assert handlers.queue(cfg)["puzzles"] == handlers.queue(cfg)["puzzles"]

    def test_hides_anything_already_decided(self, cfg):
        handlers.approve(cfg, "aaa")
        assert [p["hash"] for p in handlers.queue(cfg)["puzzles"]] == ["ccc", "bbb"]

    def test_pairs_the_chain_with_its_link_weights(self, cfg):
        # Six words, five links between them. Marking a bad link is only a
        # click if the UI can line these up without recomputing (16.2).
        puzzle = handlers.queue(cfg)["puzzles"][0]
        assert puzzle["chain"] == ["whale", "ocean", "blue", "sky", "birds", "wings"]
        assert len(puzzle["linkWeights"]) == len(puzzle["chain"]) - 1

    def test_separates_decoys_from_the_answer(self, cfg):
        puzzle = handlers.queue(cfg)["puzzles"][0]
        assert set(puzzle["decoys"]).isdisjoint(puzzle["solution"])
        assert len(puzzle["decoys"]) + len(puzzle["solution"]) == len(puzzle["bank"])

    def test_counts_every_bucket(self, cfg):
        handlers.approve(cfg, "aaa")
        handlers.reject(cfg, "bbb", "mush")
        counts = handlers.queue(cfg)["counts"]
        assert counts == {"total": 3, "pending": 1, "approved": 1, "scheduled": 0, "rejected": 1}

    def test_limit_truncates(self, cfg):
        assert len(handlers.queue(cfg, limit=2)["puzzles"]) == 2

    def test_empty_candidates_file_is_not_an_error(self, cfg):
        cfg.candidates_path.write_text("[]", encoding="utf-8")
        assert handlers.queue(cfg)["puzzles"] == []


class TestApprove:
    def test_writes_a_verdict(self, cfg):
        handlers.approve(cfg, "aaa")
        assert exporters.read_decisions(cfg.decisions_path)["aaa"].verdict == dec.ACCEPT

    def test_schedules_nothing(self, cfg):
        # The defect 7.7.3 records: approval must not imply a shipping date.
        result = handlers.approve(cfg, "aaa")
        assert result["date"] is None
        assert exporters.read_decisions(cfg.decisions_path)["aaa"].is_pooled

    def test_refuses_an_unknown_hash(self, cfg):
        with pytest.raises(handlers.BadRequest, match="no candidate"):
            handlers.approve(cfg, "nope")

    def test_refuses_to_overwrite_a_verdict(self, cfg):
        # Silently re-deciding would let a double-click undo a rejection.
        handlers.approve(cfg, "aaa")
        with pytest.raises(handlers.BadRequest, match="already has a verdict"):
            handlers.approve(cfg, "aaa")


class TestReject:
    def test_stores_reason_and_bad_link(self, cfg):
        handlers.reject(cfg, "aaa", "the sky to birds link is a stretch", bad_link=3)
        stored = exporters.read_decisions(cfg.decisions_path)["aaa"]
        assert stored.verdict == dec.REJECT
        assert stored.bad_link == 3
        assert "stretch" in (stored.reason or "")

    def test_requires_a_reason(self, cfg):
        with pytest.raises(handlers.BadRequest, match="needs a reason"):
            handlers.reject(cfg, "aaa", "   ")

    def test_rejects_an_out_of_range_link(self, cfg):
        with pytest.raises(handlers.BadRequest, match="bad_link"):
            handlers.reject(cfg, "aaa", "bad", bad_link=9)

    def test_bad_link_is_optional(self, cfg):
        handlers.reject(cfg, "aaa", "whole thing is mush")
        assert exporters.read_decisions(cfg.decisions_path)["aaa"].bad_link is None


class TestUndo:
    def test_returns_a_puzzle_to_the_queue(self, cfg):
        handlers.approve(cfg, "aaa")
        handlers.undo(cfg, "aaa")
        assert "aaa" in [p["hash"] for p in handlers.queue(cfg)["puzzles"]]
        assert "aaa" not in exporters.read_decisions(cfg.decisions_path)

    def test_undoes_a_rejection_too(self, cfg):
        handlers.reject(cfg, "aaa", "mush")
        handlers.undo(cfg, "aaa")
        assert "aaa" not in exporters.read_decisions(cfg.decisions_path)

    def test_refuses_when_there_is_nothing_to_undo(self, cfg):
        with pytest.raises(handlers.BadRequest, match="no verdict"):
            handlers.undo(cfg, "aaa")

    def test_refuses_while_scheduled(self, cfg):
        # A puzzle vanishing off the calendar as a side effect of Undo is the
        # class of bug that loses work.
        handlers.approve(cfg, "aaa")
        decisions = exporters.read_decisions(cfg.decisions_path)
        decisions["aaa"] = dec.schedule(decisions["aaa"], "2026-10-01")
        exporters.write_decisions(cfg.decisions_path, decisions)

        with pytest.raises(handlers.BadRequest, match="unschedule it first"):
            handlers.undo(cfg, "aaa")


class TestPersistence:
    def test_verdicts_survive_a_reload(self, cfg):
        handlers.approve(cfg, "aaa")
        handlers.reject(cfg, "bbb", "mush", bad_link=1)

        reloaded = exporters.read_decisions(cfg.decisions_path)
        assert reloaded["aaa"].verdict == dec.ACCEPT
        assert reloaded["bbb"].bad_link == 1

    def test_export_sees_what_the_admin_wrote(self, cfg):
        """The whole point of writing to `decisions.json` rather than a
        database: the existing pipeline picks the verdict up unchanged."""
        handlers.approve(cfg, "aaa")
        decisions = exporters.read_decisions(cfg.decisions_path)
        approved = [h for h, d in decisions.items() if d.verdict == dec.ACCEPT]
        assert approved == ["aaa"]
