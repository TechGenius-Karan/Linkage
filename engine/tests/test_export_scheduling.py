"""Export honours the dates a reviewer chose (planning.md 16.2, Phase 6c).

Auto-assignment used to be the whole story: `export` took every approval, sorted
it, and handed out consecutive dates. It is now a **proposal** -- a decision
carrying a date is a person's explicit choice and export puts that puzzle on
that day.

The invariant these tests guard is the archive's only hard one:
`date == epoch + (id - 1)` days, with no gaps. A reviewer picks a slot in a
contiguous run; they cannot punch a hole in it.
"""

from __future__ import annotations

import json

import networkx as nx
import pytest
from typer.testing import CliRunner

from linkage_engine.cli import app
from linkage_engine.config import Config
from linkage_engine.data import exporters, graph_store
from linkage_engine.domain import decisions as dec

runner = CliRunner()

TODAY = "2026-09-11"

#: Four disjoint chains, so no two candidates share a word and the corpus
#: rules never fire for reasons a scheduling test is not about.
CHAINS = {
    "aaa": ("whale", "ocean", "blue", "sky", "birds", "wings"),
    "bbb": ("piano", "music", "dance", "party", "cake", "sugar"),
    "ccc": ("engine", "motor", "wheel", "tyre", "rubber", "tree"),
    "ddd": ("letter", "word", "page", "chapter", "novel", "library"),
}


def rows() -> list[dict]:
    out = []
    for i, (hash_, chain) in enumerate(sorted(CHAINS.items())):
        out.append(
            {
                "hash": hash_,
                "start": chain[0],
                "end": chain[-1],
                "solution": list(chain[1:-1]),
                "bank": sorted([*chain[1:-1], f"decoy{i}a", f"decoy{i}b"]),
                # Descending, so auto-selection has an order to disagree with.
                "quality": 0.9 - i * 0.1,
                "weights": [3.0] * 5,
                "relations": [["RelatedTo"]] * 5,
            }
        )
    return out


@pytest.fixture
def repo(tmp_path, monkeypatch):
    cfg = Config(repo_root=tmp_path, batch_size=4, launch_week_size=2, hint_count=1)
    cfg.engine_dir.mkdir(parents=True, exist_ok=True)
    cfg.candidates_path.write_text(json.dumps(rows()), encoding="utf-8")

    graph = nx.Graph()
    for i, chain in enumerate(sorted(CHAINS.values())):
        for a, b in zip(chain, chain[1:]):
            graph.add_edge(a, b, weight=3.0, relations=("RelatedTo",))
        # Decoys hang off one solution word and go nowhere, so every bank has
        # exactly one arrangement -- the property `write_puzzles` assumes.
        graph.add_edge(chain[1], f"decoy{i}a", weight=2.0, relations=("RelatedTo",))
        graph.add_edge(chain[2], f"decoy{i}b", weight=2.0, relations=("RelatedTo",))
    graph_store.save(
        graph,
        cfg.graph_path,
        graph_store.build_meta(cfg, conceptnet_sha256="test", vocab_size=len(graph)),
    )

    monkeypatch.setattr("linkage_engine.cli.DEFAULT", cfg)
    return cfg


def decide(cfg: Config, **verdicts: str | None) -> None:
    """`hash=None` approves and leaves it undated; `hash="2026-10-03"` pins it."""
    decisions = {}
    for hash_, when in verdicts.items():
        decision = dec.approve(TODAY)
        decisions[hash_] = dec.schedule(decision, when) if when else decision
    exporters.write_decisions(cfg.decisions_path, decisions)


def run(*args: str):
    result = runner.invoke(app, ["export", *args])
    return result


def shipped(cfg: Config) -> dict[str, str]:
    """date -> start word, which is enough to identify which puzzle landed."""
    return {p.date: p.start for p in exporters.read_archive(cfg)}


class TestPinnedDates:
    def test_a_scheduled_puzzle_lands_on_its_date(self, repo):
        decide(repo, aaa="2026-10-03", bbb=None, ccc=None, ddd=None)
        assert run().exit_code == 0
        assert shipped(repo)["2026-10-03"] == "whale"

    def test_the_rest_of_the_run_fills_around_it(self, repo):
        decide(repo, aaa="2026-10-03", bbb=None, ccc=None, ddd=None)
        run()
        assert sorted(shipped(repo)) == [
            "2026-10-01",
            "2026-10-02",
            "2026-10-03",
            "2026-10-04",
        ]

    def test_no_puzzle_ships_twice(self, repo):
        decide(repo, aaa="2026-10-03", bbb=None, ccc=None, ddd=None)
        run()
        starts = list(shipped(repo).values())
        assert len(set(starts)) == len(starts)

    def test_every_slot_can_be_pinned(self, repo):
        decide(
            repo,
            aaa="2026-10-04",
            bbb="2026-10-03",
            ccc="2026-10-02",
            ddd="2026-10-01",
        )
        assert run().exit_code == 0
        assert shipped(repo) == {
            "2026-10-01": "letter",
            "2026-10-02": "engine",
            "2026-10-03": "piano",
            "2026-10-04": "whale",
        }

    def test_the_id_and_the_date_stay_in_step(self, repo):
        # The golden invariant. A drift here shows the wrong puzzle number in
        # every share anyone posts.
        decide(repo, aaa="2026-10-04", bbb=None, ccc=None, ddd=None)
        run()
        archive = exporters.read_archive(repo)
        assert [(p.id, p.date) for p in archive] == [
            (1, "2026-10-01"),
            (2, "2026-10-02"),
            (3, "2026-10-03"),
            (4, "2026-10-04"),
        ]

    def test_an_unpinned_batch_still_works_exactly_as_before(self, repo):
        decide(repo, aaa=None, bbb=None, ccc=None, ddd=None)
        assert run().exit_code == 0
        assert len(shipped(repo)) == 4


class TestTheRunStaysUnbroken:
    def test_a_pin_past_a_gap_is_reported_rather_than_silently_dropped(self, repo):
        # Two free puzzles fill 10-01 and 10-02; nothing is left for 10-03, so
        # the run stops there. Shipping `aaa` on 10-04 anyway would break
        # `date == epoch + id - 1` for it and for everything after it.
        decide(repo, aaa="2026-10-04", bbb=None, ccc=None)
        result = run()
        assert result.exit_code == 0
        assert "will not ship" in result.output
        assert "2026-10-04" not in shipped(repo)

    def test_and_what_did_ship_is_still_contiguous(self, repo):
        decide(repo, aaa="2026-10-04", bbb=None, ccc=None)
        run()
        assert sorted(shipped(repo)) == ["2026-10-01", "2026-10-02"]

    def test_a_pin_past_the_end_of_the_batch_is_reported(self, repo):
        # Silently ignoring it would look identical, from the output, to
        # having shipped it.
        decide(repo, aaa="2026-10-04", bbb=None)
        result = runner.invoke(app, ["export", "--count", "2"])
        assert "past this batch" in result.output

    def test_a_date_the_archive_already_covers_is_refused(self, repo):
        decide(repo, aaa=None, bbb=None)
        run()
        decide(repo, aaa="2026-10-01", ccc=None)
        result = run()
        assert result.exit_code == 1
        assert "already covered by the archive" in result.output


class TestBankEdits:
    def test_a_hand_swapped_bank_is_what_ships(self, repo):
        # The swap lives on the decision and is replayed here, because the
        # content hash covers the bank -- rewriting candidates.json in place
        # would orphan the decision holding the edit (planning.md 16.4).
        decisions = {
            "aaa": dec.approve(
                TODAY, edits=(dec.BankEdit(removed="decoy0a", added="decoy1a"),)
            )
        }
        exporters.write_decisions(repo.decisions_path, decisions)
        assert run().exit_code == 0
        puzzle = exporters.read_archive(repo)[0]
        assert "decoy1a" in puzzle.bank
        assert "decoy0a" not in puzzle.bank

    def test_the_candidate_file_is_never_rewritten(self, repo):
        before = repo.candidates_path.read_text(encoding="utf-8")
        decisions = {
            "aaa": dec.approve(
                TODAY, edits=(dec.BankEdit(removed="decoy0a", added="decoy1a"),)
            )
        }
        exporters.write_decisions(repo.decisions_path, decisions)
        run()
        assert repo.candidates_path.read_text(encoding="utf-8") == before
