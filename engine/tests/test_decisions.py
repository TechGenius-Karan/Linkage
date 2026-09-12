"""The review state machine (planning.md 16.2)."""

from __future__ import annotations

import pytest

from linkage_engine.domain import decisions as d

TODAY = "2026-09-10"


def approved() -> d.Decision:
    return d.approve(TODAY)


def scheduled(date: str = "2026-10-08") -> d.Decision:
    return d.schedule(approved(), date)


class TestApprove:
    def test_records_taste_and_nothing_else(self):
        # The whole point of 16.2: approving must not imply a shipping date.
        decision = approved()
        assert decision.verdict == d.ACCEPT
        assert decision.date is None
        assert decision.is_pooled
        assert not decision.is_scheduled

    def test_carries_swaps_made_during_review(self):
        edits = (d.BankEdit("wave", "reef"),)
        assert d.approve(TODAY, edits=edits).bank_edits == edits


class TestReject:
    def test_needs_a_reason(self):
        # A rejection with no reason teaches the next generation nothing, and
        # rebuilding the scorer from verdicts is the reason they are stored.
        with pytest.raises(d.DecisionError, match="needs a reason"):
            d.reject(TODAY, reason="   ")

    def test_records_which_link_failed(self):
        decision = d.reject(TODAY, reason="sailing to fun is a stretch", bad_link=2)
        assert decision.bad_link == 2

    def test_bad_link_is_optional(self):
        assert d.reject(TODAY, reason="whole chain is mush").bad_link is None

    @pytest.mark.parametrize("index", [-1, 5, 99])
    def test_rejects_an_out_of_range_link(self, index):
        with pytest.raises(d.DecisionError, match="bad_link"):
            d.reject(TODAY, reason="x", bad_link=index)

    @pytest.mark.parametrize("index", [0, 4])
    def test_accepts_both_ends_of_the_chain(self, index):
        # Five edges, so the opening and closing moves are both reportable.
        assert d.reject(TODAY, reason="x", bad_link=index).bad_link == index

    def test_cannot_hold_a_date(self):
        with pytest.raises(d.DecisionError, match="cannot hold a date"):
            d.Decision(verdict="reject", decided_at=TODAY, reason="x", date="2026-10-01")

    def test_trims_the_reason(self):
        assert d.reject(TODAY, reason="  weak link  ").reason == "weak link"


class TestSchedule:
    def test_puts_an_approved_puzzle_on_a_date(self):
        decision = scheduled("2026-10-08")
        assert decision.date == "2026-10-08"
        assert decision.is_scheduled
        assert not decision.is_pooled

    def test_refuses_a_rejected_puzzle(self):
        rejected = d.reject(TODAY, reason="no")
        with pytest.raises(d.DecisionError, match="only an approved"):
            d.schedule(rejected, "2026-10-08")

    def test_refuses_to_double_book_one_puzzle(self):
        with pytest.raises(d.DecisionError, match="already scheduled"):
            d.schedule(scheduled(), "2026-10-09")

    def test_unschedule_returns_it_to_the_pool_still_approved(self):
        # Not the same as unapproving -- the reviewer still likes the puzzle.
        back = d.unschedule(scheduled())
        assert back.is_pooled
        assert back.verdict == d.ACCEPT

    def test_unschedule_refuses_an_unscheduled_puzzle(self):
        with pytest.raises(d.DecisionError, match="not scheduled"):
            d.unschedule(approved())

    def test_scheduling_preserves_the_review_record(self):
        edits = (d.BankEdit("wave", "reef"),)
        decision = d.schedule(d.approve(TODAY, edits=edits), "2026-10-08")
        assert decision.bank_edits == edits
        assert decision.decided_at == TODAY


class TestUnapprove:
    def test_refuses_while_still_on_the_calendar(self):
        # A puzzle vanishing from the schedule as a side effect of a different
        # button is exactly the class of bug that loses work.
        with pytest.raises(d.DecisionError, match="unschedule it first"):
            d.unapprove(scheduled())

    def test_allows_an_undated_approval(self):
        assert d.unapprove(approved()).verdict == d.ACCEPT

    def test_refuses_a_rejection(self):
        with pytest.raises(d.DecisionError, match="not approved"):
            d.unapprove(d.reject(TODAY, reason="no"))


class TestSwaps:
    def test_appends_in_order(self):
        decision = d.record_swap(d.record_swap(approved(), "wave", "reef"), "salt", "kelp")
        assert [(e.removed, e.added) for e in decision.bank_edits] == [
            ("wave", "reef"),
            ("salt", "kelp"),
        ]

    def test_refuses_a_no_op(self):
        with pytest.raises(d.DecisionError, match="changes nothing"):
            d.record_swap(approved(), "wave", "wave")


class TestSerialisation:
    def test_round_trips(self):
        original = d.record_swap(
            d.schedule(d.approve(TODAY), "2026-10-08"), "wave", "reef"
        )
        assert d.from_json(d.to_json(original)) == original

    def test_round_trips_a_rejection(self):
        original = d.reject(TODAY, reason="weak link", bad_link=3)
        assert d.from_json(d.to_json(original)) == original

    def test_reads_approve_as_a_spelling_of_accept(self):
        # Hand-written review files use "approve"; refusing to load over one
        # synonym would lose a reviewer's work on a technicality.
        assert d.from_json({"verdict": "approve", "decidedAt": TODAY}).verdict == d.ACCEPT

    def test_rejects_a_verdict_it_does_not_know(self):
        with pytest.raises(d.DecisionError, match="unknown verdict"):
            d.from_json({"verdict": "maybe", "decidedAt": TODAY})

    def test_reads_the_old_flat_shape(self):
        # decisions.json used to map a hash straight to a verdict string. A file
        # written by the terminal TUI must still load rather than crashing the
        # tool that replaced it.
        decision = d.from_json("accept")
        assert decision.verdict == d.ACCEPT
        assert decision.date is None

    def test_tolerates_missing_fields(self):
        decision = d.from_json({"verdict": "approve", "decidedAt": TODAY})
        assert decision.bank_edits == ()
        assert decision.reason is None

    def test_skips_malformed_bank_edits_rather_than_crashing(self):
        decision = d.from_json(
            {
                "verdict": "approve",
                "decidedAt": TODAY,
                "bankEdits": [{"removed": "wave", "added": "reef"}, {"oops": 1}, "nonsense"],
            }
        )
        assert len(decision.bank_edits) == 1

    def test_rejects_a_shape_it_cannot_read(self):
        with pytest.raises(d.DecisionError):
            d.from_json(42)


class TestViews:
    def build(self) -> dict[str, d.Decision]:
        return {
            "aaa": d.schedule(d.approve(TODAY), "2026-10-02"),
            "bbb": d.approve(TODAY),
            "ccc": d.reject(TODAY, reason="mush"),
            "ddd": d.schedule(d.approve(TODAY), "2026-10-01"),
            "eee": d.approve(TODAY),
        }

    def test_splits_by_state(self):
        split = d.split(self.build())
        assert split.approved_pool == ("bbb", "eee")
        assert split.rejected == ("ccc",)
        assert set(split.scheduled) == {"aaa", "ddd"}

    def test_scheduled_is_ordered_by_date(self):
        # A queue that reorders itself between reloads is one a reviewer loses
        # their place in.
        assert d.split(self.build()).scheduled == ("ddd", "aaa")

    def test_empty_set_is_empty(self):
        split = d.split({})
        assert split.approved_pool == () and split.scheduled == () and split.rejected == ()

    def test_taken_dates_maps_day_to_puzzle(self):
        assert d.taken_dates(self.build()) == {"2026-10-02": "aaa", "2026-10-01": "ddd"}

    def test_taken_dates_catches_a_double_booking(self):
        clash = {
            "aaa": d.schedule(d.approve(TODAY), "2026-10-02"),
            "bbb": d.schedule(d.approve(TODAY), "2026-10-02"),
        }
        with pytest.raises(d.DecisionError, match="already holds"):
            d.taken_dates(clash)


class TestApplyEdits:
    """Replaying swaps over the generated bank (planning.md 16.4).

    The edits live on the decision, never on the candidate, because
    `Candidate.content_hash()` covers the bank -- rewriting it in place would
    change the hash and orphan the judgement the swap was part of.
    """

    BANK = ("blue", "cloud", "nest", "ocean", "sky")

    def test_no_edits_is_the_bank_itself(self):
        assert d.apply_edits(self.BANK, ()) == self.BANK

    def test_one_swap(self):
        edits = (d.BankEdit(removed="nest", added="wave"),)
        assert d.apply_edits(self.BANK, edits) == ("blue", "cloud", "ocean", "sky", "wave")

    def test_swaps_replay_in_order(self):
        edits = (
            d.BankEdit(removed="nest", added="wave"),
            d.BankEdit(removed="wave", added="tide"),
        )
        assert d.apply_edits(self.BANK, edits) == ("blue", "cloud", "ocean", "sky", "tide")

    def test_the_size_never_changes(self):
        edits = (d.BankEdit(removed="nest", added="wave"),)
        assert len(d.apply_edits(self.BANK, edits)) == len(self.BANK)

    def test_the_result_is_sorted(self):
        # A bank whose order depended on edit history would make the export
        # non-deterministic (planning.md 7.8).
        edits = (d.BankEdit(removed="blue", added="zephyr"),)
        out = d.apply_edits(self.BANK, edits)
        assert list(out) == sorted(out)

    def test_an_edit_that_no_longer_applies_is_loud(self):
        # Silence here would ship a bank the reviewer never approved.
        edits = (d.BankEdit(removed="absent", added="wave"),)
        with pytest.raises(d.DecisionError, match="not in the bank"):
            d.apply_edits(self.BANK, edits)

    def test_a_replay_that_would_duplicate_a_word_is_loud(self):
        edits = (d.BankEdit(removed="nest", added="sky"),)
        with pytest.raises(d.DecisionError, match="duplicate"):
            d.apply_edits(self.BANK, edits)

    def test_an_approval_carries_its_edits(self):
        edits = (d.BankEdit(removed="nest", added="wave"),)
        decision = d.approve(TODAY, edits=edits)
        assert decision.bank_edits == edits
        assert d.from_json(d.to_json(decision)).bank_edits == edits


class TestEveryVerdictSurvivesTheFile:
    """A verdict that writes but cannot be read back makes `decisions.json`
    unloadable -- and that file is durable human judgement, not a cache.

    Parametrised over the whole `Verdict` union rather than listing the ones
    that exist today: `revisit` was added to the union, to `__post_init__` and
    to the transitions, but not to the *parser*, and every hand-written test
    passed while the tool could not reload its own output.
    """

    @pytest.mark.parametrize("verdict", [d.ACCEPT, d.REJECT, d.REVISIT])
    def test_round_trips(self, verdict):
        built = {
            d.ACCEPT: lambda: d.approve(TODAY),
            d.REJECT: lambda: d.reject(TODAY, reason="mush"),
            d.REVISIT: lambda: d.revisit(TODAY, d.approve(TODAY)),
        }[verdict]()
        assert d.from_json(d.to_json(built)) == built

    def test_the_union_and_the_parser_agree(self):
        # The actual defect: three places knew about `revisit` and the fourth
        # did not. This fails the moment they diverge again.
        from typing import get_args

        for verdict in get_args(d.Verdict):
            assert d._verdict(verdict) == verdict

    def test_an_unknown_verdict_is_still_refused(self):
        with pytest.raises(d.DecisionError, match="unknown verdict"):
            d.from_json({"verdict": "maybe"})
