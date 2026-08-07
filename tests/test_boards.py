"""Status board validation: the board schema, and the rules it cannot express.

A board holds no evidence of its own, so the whole question a board suite has
to answer is whether every row rests on something -- a record, or a quoted
source -- and whether the plain-language status fields are held to the same
standard as the record-page strip they mirror.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from significance.boards import board_violations, is_board, load_board
from significance.validate import validate_paths

REPO_ROOT = Path(__file__).resolve().parents[1]
BOARD = REPO_ROOT / "boards" / "ten-results.yaml"
BROKEN_BOARDS = REPO_ROOT / "tests" / "fixtures" / "broken-boards"
EXAMPLE_RECORD = REPO_ROOT / "examples" / "synthetic-ramsey-k7.yaml"


def _rules(violations):
    return {v.rule for v in violations}


def test_the_shipped_board_validates():
    violations = board_violations(load_board(BOARD))
    assert violations == [], "\n".join(str(v) for v in violations)


def test_the_shipped_board_fills_exactly_one_row():
    # The intended state of the file, not an unfinished draft: nothing in this
    # repository evidences the other nine results, so nothing on the board says
    # anything about them.
    board = load_board(BOARD)
    assert len(board["rows"]) == 10
    recorded = [r for r in board["rows"] if r["state"] == "recorded"]
    assert len(recorded) == 1
    assert recorded[0]["record"] == "2026-openai-nonsofic-groups"

    for row in board["rows"]:
        if row["state"] != "placeholder":
            continue
        assert "claim" not in row, "a placeholder row must assert nothing"
        assert "status" not in row
        assert row["result"].lower().startswith("[fill")


def test_the_board_row_matches_the_record_it_links():
    # The row restates the record; it must not drift from it. A board that
    # quietly disagreed with the record behind it would be the worst of both.
    from significance.records import load_record

    board = load_board(BOARD)
    row = next(r for r in board["rows"] if r.get("record"))
    record = load_record(REPO_ROOT / "records" / f"{row['record']}.yaml")
    assert row["claim"]["value"] == record["claim"]["text"]["value"]
    assert row["claim"]["locator"]["quote"] == record["claim"]["text"]["locator"]["quote"]
    assert row["artifacts"]["manuscript"] == record["manuscript"]["url"]


@pytest.mark.parametrize(
    "fixture_name,expected_rule",
    [
        ("row-without-source.yaml", "row-without-source"),
        ("placeholder-looks-filled.yaml", "placeholder-row-looks-filled"),
    ],
)
def test_broken_board_fixture(fixture_name, expected_rule):
    violations = validate_paths([str(BROKEN_BOARDS / fixture_name)])
    assert _rules(violations) == {expected_rule}, [str(v) for v in violations]


def test_a_row_status_with_no_attribution_is_refused():
    violations = validate_paths([str(BROKEN_BOARDS / "row-missing-attribution.yaml")])
    assert _rules(violations) == {"unattributed-assertion"}


def test_verdict_language_is_refused_in_a_row_status():
    board = load_board(BOARD)
    row = next(r for r in board["rows"] if r.get("status"))
    row["status"]["checked"] = "The build ran and the theorem is true."
    assert _rules(board_violations(board)) == {"verdict-language"}


def test_verdict_language_is_refused_in_the_board_intro():
    board = load_board(BOARD)
    board["intro"]["value"] = "Nine of these results are correct."
    assert _rules(board_violations(board)) == {"verdict-language"}


def test_a_row_may_not_list_only_what_was_checked():
    board = load_board(BOARD)
    row = next(r for r in board["rows"] if r.get("status"))
    row["status"]["not_checked"] = "  "
    assert "row-status-understates-open-work" in _rules(board_violations(board))


def test_status_fields_answer_to_the_same_word_cap_as_the_record_strip():
    from significance.semantics import PLAIN_SUMMARY_MAX_WORDS

    board = load_board(BOARD)
    row = next(r for r in board["rows"] if r.get("status"))
    row["status"]["checked"] = " ".join(["word"] * (PLAIN_SUMMARY_MAX_WORDS + 1))
    assert "plain-summary-too-long" in _rules(board_violations(board))


def test_asserted_by_must_resolve_to_a_declared_party():
    board = load_board(BOARD)
    board["rows"][0]["status"]["asserted_by"] = "nobody-declared"
    assert "unknown-party" in _rules(board_violations(board))


def test_a_record_is_not_mistaken_for_a_board_or_the_reverse():
    # The discriminator is explicit rather than sniffed, so a record with an
    # unusual shape fails as the record it is instead of being quietly checked
    # against the wrong schema.
    from significance.records import load_record

    assert is_board(load_board(BOARD)) is True
    assert is_board(load_record(EXAMPLE_RECORD)) is False

    # And a directory holding both validates each against its own rules.
    violations = validate_paths([str(EXAMPLE_RECORD), str(BOARD)])
    assert violations == [], [str(v) for v in violations]
