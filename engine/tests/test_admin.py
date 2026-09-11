"""The admin's handlers (planning.md 16.3).

No HTTP here: the handlers are plain functions taking a Config, which is the
reason `server.py` holds the socket and nothing else.
"""

from __future__ import annotations

import json

import networkx as nx
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


# --------------------------------------------------------------------------
# 6b -- refining a bank (planning.md 16.4)
# --------------------------------------------------------------------------


@pytest.fixture
def graph():
    """The fixture chain, its decoys, and one word that breaks uniqueness.

    `whale - ocean - blue - sky - birds - wings` is the solution. Every decoy
    in the fixture bank hangs off one solution word and goes nowhere, so the
    bank as generated has exactly one arrangement.

    `wave` is the exception and is deliberately **not** in the bank: it is
    wired `whale - wave - blue`, so admitting it would make
    `whale - wave - blue - sky - birds - wings` a second valid answer. It is
    what every veto test swaps in.
    """
    g = nx.Graph()
    chain = ("whale", "ocean", "blue", "sky", "birds", "wings")
    for a, b in zip(chain, chain[1:]):
        g.add_edge(a, b, weight=3.0, relations=("RelatedTo",))
    for anchor, decoy in (
        ("ocean", "cloud"),
        ("ocean", "sea"),
        ("sky", "shark"),
        ("birds", "nest"),
        ("blue", "storm"),
        ("sky", "planet"),
    ):
        g.add_edge(anchor, decoy, weight=2.0, relations=("RelatedTo",))
    g.add_edge("whale", "wave", weight=3.0, relations=("RelatedTo",))
    g.add_edge("wave", "blue", weight=3.0, relations=("RelatedTo",))
    return g


def edit(removed: str, added: str) -> dec.BankEdit:
    return dec.BankEdit(removed=removed, added=added)


class TestSwap:
    def test_previews_the_edited_bank(self, cfg, graph):
        result = handlers.swap(cfg, graph, "aaa", (edit("cloud", "storm"),))
        assert "storm" in result["bank"]
        assert "cloud" not in result["bank"]

    def test_writes_nothing(self, cfg, graph):
        # A swap is a preview until the reviewer approves the puzzle it made.
        # That is what keeps the state machine at three states instead of four.
        handlers.swap(cfg, graph, "aaa", (edit("cloud", "storm"),))
        assert not cfg.decisions_path.exists()
        assert handlers.queue(cfg)["counts"]["pending"] == 3

    def test_refuses_a_swap_that_creates_a_second_solution(self, cfg, graph):
        with pytest.raises(handlers.BadRequest, match="second valid solution"):
            handlers.swap(cfg, graph, "aaa", (edit("cloud", "wave"),))

    def test_a_refused_swap_leaves_the_puzzle_in_the_queue(self, cfg, graph):
        with pytest.raises(handlers.BadRequest):
            handlers.swap(cfg, graph, "aaa", (edit("cloud", "wave"),))
        assert "aaa" in [p["hash"] for p in handlers.queue(cfg)["puzzles"]]

    def test_names_which_swap_was_refused_not_just_that_one_was(self, cfg, graph):
        with pytest.raises(handlers.BadRequest, match="wave"):
            handlers.swap(cfg, graph, "aaa", (edit("cloud", "storm"), edit("shark", "wave")))

    def test_refuses_to_touch_a_rejected_puzzle(self, cfg, graph):
        handlers.reject(cfg, "aaa", "weak opening", 0)
        with pytest.raises(handlers.BadRequest, match="rejected"):
            handlers.swap(cfg, graph, "aaa", (edit("cloud", "storm"),))


class TestSwapOptions:
    def test_offers_only_words_the_engine_would_accept(self, cfg, graph):
        options = handlers.swap_options(cfg, graph, "aaa", "cloud")["options"]
        assert options
        for option in options:
            handlers.swap(cfg, graph, "aaa", (edit("cloud", option["word"]),))

    def test_never_offers_the_word_that_breaks_uniqueness(self, cfg, graph):
        options = handlers.swap_options(cfg, graph, "aaa", "cloud")["options"]
        assert "wave" not in {o["word"] for o in options}

    def test_shows_the_temptingness_so_softening_is_visible(self, cfg, graph):
        options = handlers.swap_options(cfg, graph, "aaa", "cloud")["options"]
        assert all("temptingness" in o and "source" in o for o in options)

    def test_accounts_for_edits_the_reviewer_has_not_saved_yet(self, cfg, graph):
        # `storm` went into the bank a moment ago and has not been written
        # anywhere yet. Offering it again would let one reviewer, in one
        # sitting, put the same word in the bank twice.
        pending = (edit("cloud", "storm"),)
        options = handlers.swap_options(cfg, graph, "aaa", "shark", pending)["options"]
        assert "storm" not in {o["word"] for o in options}

    def test_rejects_a_word_that_is_not_in_the_bank(self, cfg, graph):
        with pytest.raises(handlers.BadRequest, match="not in the bank"):
            handlers.swap_options(cfg, graph, "aaa", "absent")


class TestApproveWithEdits:
    def test_stores_the_edits_on_the_decision(self, cfg, graph):
        handlers.approve(cfg, "aaa", edits=(edit("cloud", "storm"),), graph=graph)
        stored = exporters.read_decisions(cfg.decisions_path)["aaa"]
        assert stored.verdict == dec.ACCEPT
        assert stored.bank_edits == (dec.BankEdit("cloud", "storm"),)

    def test_the_candidate_file_is_never_rewritten(self, cfg, graph):
        # The content hash covers the bank. Editing candidates.json in place
        # would change the hash and orphan the decision holding the edit.
        before = cfg.candidates_path.read_text(encoding="utf-8")
        handlers.approve(cfg, "aaa", edits=(edit("cloud", "storm"),), graph=graph)
        assert cfg.candidates_path.read_text(encoding="utf-8") == before

    def test_reproves_the_edits_rather_than_trusting_the_client(self, cfg, graph):
        # `swap` already proved them, and this is the one property the whole
        # game rests on -- a client that skipped the preview must not get past.
        with pytest.raises(handlers.BadRequest, match="second valid solution"):
            handlers.approve(cfg, "aaa", edits=(edit("cloud", "wave"),), graph=graph)
        assert not cfg.decisions_path.exists()

    def test_the_pool_shows_the_edited_bank(self, cfg, graph):
        handlers.approve(cfg, "aaa", edits=(edit("cloud", "storm"),), graph=graph)
        view = handlers.pool(cfg)["pooled"][0]
        assert "storm" in view["bank"] and "cloud" not in view["bank"]
        assert view["bankEdits"] == [{"removed": "cloud", "added": "storm"}]


# --------------------------------------------------------------------------
# 6c -- the pool, and choosing a date (planning.md 16.2, 16.6)
# --------------------------------------------------------------------------


class TestPool:
    def test_approving_puts_a_puzzle_in_the_pool_with_no_date(self, cfg):
        handlers.approve(cfg, "aaa")
        pool = handlers.pool(cfg)
        assert [p["hash"] for p in pool["pooled"]] == ["aaa"]
        assert pool["pooled"][0]["date"] is None
        assert pool["scheduled"] == []

    def test_the_pool_is_ordered_best_first(self, cfg):
        for h in ("aaa", "bbb", "ccc"):
            handlers.approve(cfg, h)
        assert [p["hash"] for p in handlers.pool(cfg)["pooled"]] == ["aaa", "ccc", "bbb"]

    def test_offers_a_contiguous_run_of_slots(self, cfg):
        # Dates are not free-form: `date == epoch + (id - 1)` days is the
        # archive's one hard invariant, so a puzzle occupies a slot in an
        # unbroken run rather than any day the reviewer fancies.
        slots = handlers.pool(cfg)["slots"]
        assert [s["date"] for s in slots[:3]] == ["2026-10-01", "2026-10-02", "2026-10-03"]
        assert all(s["hash"] is None for s in slots)

    def test_a_scheduled_puzzle_claims_its_slot(self, cfg):
        handlers.approve(cfg, "aaa")
        handlers.schedule(cfg, "aaa", "2026-10-02")
        pool = handlers.pool(cfg)
        assert [s["hash"] for s in pool["slots"][:3]] == [None, "aaa", None]
        assert [p["hash"] for p in pool["scheduled"]] == ["aaa"]
        assert pool["pooled"] == []

    def test_rejected_puzzles_never_appear(self, cfg):
        handlers.reject(cfg, "aaa", "the opening link is a stretch", 0)
        pool = handlers.pool(cfg)
        assert pool["pooled"] == [] and pool["scheduled"] == []


class TestSchedule:
    def test_puts_an_approved_puzzle_on_a_date(self, cfg):
        handlers.approve(cfg, "aaa")
        assert handlers.schedule(cfg, "aaa", "2026-10-03")["date"] == "2026-10-03"
        assert exporters.read_decisions(cfg.decisions_path)["aaa"].date == "2026-10-03"

    def test_refuses_a_puzzle_that_was_never_approved(self, cfg):
        with pytest.raises(handlers.BadRequest, match="only an approved puzzle"):
            handlers.schedule(cfg, "aaa", "2026-10-01")

    def test_refuses_a_rejected_puzzle(self, cfg):
        handlers.reject(cfg, "aaa", "the chain breaks at the second rung", 1)
        with pytest.raises(handlers.BadRequest, match="only an approved puzzle"):
            handlers.schedule(cfg, "aaa", "2026-10-01")

    def test_refuses_a_day_that_is_already_taken(self, cfg):
        handlers.approve(cfg, "aaa")
        handlers.approve(cfg, "bbb")
        handlers.schedule(cfg, "aaa", "2026-10-01")
        with pytest.raises(handlers.BadRequest, match="already holds aaa"):
            handlers.schedule(cfg, "bbb", "2026-10-01")

    def test_refuses_a_date_outside_the_run(self, cfg):
        # A date export can never reach would silently do nothing, which is
        # worse than a refusal the reviewer can see.
        handlers.approve(cfg, "aaa")
        with pytest.raises(handlers.BadRequest, match="not an open slot"):
            handlers.schedule(cfg, "aaa", "2029-01-01")

    def test_refuses_to_reschedule_without_unscheduling(self, cfg):
        handlers.approve(cfg, "aaa")
        handlers.schedule(cfg, "aaa", "2026-10-01")
        with pytest.raises(handlers.BadRequest, match="already scheduled"):
            handlers.schedule(cfg, "aaa", "2026-10-02")

    def test_warns_about_a_duplicate_endpoint_pair_while_the_day_can_change(self, cfg):
        # 16.6's whole argument: the export check, asked early enough to act on.
        handlers.approve(cfg, "aaa")
        handlers.approve(cfg, "bbb")
        handlers.schedule(cfg, "aaa", "2026-10-01")
        warnings = handlers.schedule(cfg, "bbb", "2026-10-02")["warnings"]
        assert any("whale" in w and "wings" in w for w in warnings)

    def test_the_warning_never_blocks_the_schedule(self, cfg):
        handlers.approve(cfg, "aaa")
        handlers.approve(cfg, "bbb")
        handlers.schedule(cfg, "aaa", "2026-10-01")
        handlers.schedule(cfg, "bbb", "2026-10-02")
        assert exporters.read_decisions(cfg.decisions_path)["bbb"].date == "2026-10-02"

    def test_a_clean_date_warns_about_nothing(self, cfg):
        handlers.approve(cfg, "aaa")
        assert handlers.schedule(cfg, "aaa", "2026-10-01")["warnings"] == []


class TestUnschedule:
    def test_returns_a_puzzle_to_the_undated_pool(self, cfg):
        handlers.approve(cfg, "aaa")
        handlers.schedule(cfg, "aaa", "2026-10-01")
        assert handlers.unschedule(cfg, "aaa")["date"] is None
        pool = handlers.pool(cfg)
        assert [p["hash"] for p in pool["pooled"]] == ["aaa"]
        assert pool["scheduled"] == []

    def test_keeps_the_approval(self, cfg):
        # Deliberately not the same act as unapproving: the reviewer still
        # likes the puzzle, they just want a different day for it.
        handlers.approve(cfg, "aaa")
        handlers.schedule(cfg, "aaa", "2026-10-01")
        handlers.unschedule(cfg, "aaa")
        assert exporters.read_decisions(cfg.decisions_path)["aaa"].verdict == dec.ACCEPT

    def test_frees_the_day_for_something_else(self, cfg):
        handlers.approve(cfg, "aaa")
        handlers.approve(cfg, "bbb")
        handlers.schedule(cfg, "aaa", "2026-10-01")
        handlers.unschedule(cfg, "aaa")
        assert handlers.schedule(cfg, "bbb", "2026-10-01")["date"] == "2026-10-01"

    def test_refuses_a_puzzle_that_is_not_scheduled(self, cfg):
        handlers.approve(cfg, "aaa")
        with pytest.raises(handlers.BadRequest, match="not scheduled"):
            handlers.unschedule(cfg, "aaa")


class TestUnapprove:
    def test_undo_refuses_while_the_puzzle_is_on_the_calendar(self, cfg):
        # A puzzle vanishing from the calendar as a side effect of a different
        # button is exactly the class of bug that loses work.
        handlers.approve(cfg, "aaa")
        handlers.schedule(cfg, "aaa", "2026-10-01")
        with pytest.raises(handlers.BadRequest, match="unschedule it first"):
            handlers.undo(cfg, "aaa")

    def test_undo_works_once_it_is_unscheduled(self, cfg):
        handlers.approve(cfg, "aaa")
        handlers.schedule(cfg, "aaa", "2026-10-01")
        handlers.unschedule(cfg, "aaa")
        handlers.undo(cfg, "aaa")
        assert "aaa" in [p["hash"] for p in handlers.queue(cfg)["puzzles"]]
