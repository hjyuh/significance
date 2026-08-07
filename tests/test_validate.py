"""Phase 2 tests: `significance validate`'s schema + semantic rules,
covering all ten broken-fixture scenarios named in the design doc.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from significance.records import load_record
from significance.semantics import PLAIN_SUMMARY_MAX_WORDS, semantic_violations
from significance.validate import validate_paths

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_RECORD = REPO_ROOT / "examples" / "synthetic-ramsey-k7.yaml"
BROKEN_DIR = REPO_ROOT / "tests" / "fixtures" / "broken"


def _rules(violations):
    return {v.rule for v in violations}


def test_valid_record_has_no_violations():
    violations = validate_paths([str(EXAMPLE_RECORD)])
    assert violations == [], "\n".join(str(v) for v in violations)


@pytest.mark.parametrize(
    "fixture_name,expected_rule",
    [
        ("unattributed-assertion.yaml", "unattributed-assertion"),
        ("stale-confirmation-rendered-current.yaml", "stale-rendered-current"),
        ("missing-manuscript-hash.yaml", "missing-manuscript-hash"),
        ("correspondence-no-basis.yaml", "correspondence-unattested"),
        ("correspondence-machine-asserted.yaml", "correspondence-unattested"),
        ("derived-value-not-matching-recomputation.yaml", "derived-value-mismatch"),
        ("bare-result-passed-no-receipt.yaml", "bare-machine-result"),
        ("execution-receipt-asserted-by-human.yaml", "execution-receipt-not-automation"),
        ("plain-summary-verdict.yaml", "verdict-language"),
    ],
)
def test_single_record_broken_fixture(fixture_name, expected_rule):
    violations = validate_paths([str(BROKEN_DIR / fixture_name)])
    assert _rules(violations) == {expected_rule}, (
        f"{fixture_name}: expected exactly {{{expected_rule!r}}}, got {_rules(violations)}"
    )


def test_mutated_historical_event():
    violations = validate_paths(
        [str(BROKEN_DIR / "append-only" / "mutated-event.yaml")],
        base=str(BROKEN_DIR / "append-only" / "base.yaml"),
    )
    assert "history-event-mutated" in _rules(violations)


def test_deleted_event_id():
    violations = validate_paths(
        [str(BROKEN_DIR / "append-only" / "deleted-event.yaml")],
        base=str(BROKEN_DIR / "append-only" / "base.yaml"),
    )
    assert "history-event-deleted" in _rules(violations)


def test_non_monotonic_record_version():
    violations = validate_paths(
        [str(BROKEN_DIR / "append-only" / "non-monotonic-version.yaml")],
        base=str(BROKEN_DIR / "append-only" / "base.yaml"),
    )
    assert "non-monotonic-record-version" in _rules(violations)
    assert "history-event-mutated" not in _rules(violations)
    assert "history-event-deleted" not in _rules(violations)


def test_duplicate_record_id():
    violations = validate_paths([str(BROKEN_DIR / "duplicate-record-id")])
    assert _rules(violations) == {"duplicate-record-id"}
    assert len(violations) == 2
    files = {v.file for v in violations}
    assert files == {
        str(BROKEN_DIR / "duplicate-record-id" / "a.yaml"),
        str(BROKEN_DIR / "duplicate-record-id" / "b.yaml"),
    }


def test_append_only_with_no_changes_is_clean():
    violations = validate_paths(
        [str(BROKEN_DIR / "append-only" / "base.yaml")],
        base=str(BROKEN_DIR / "append-only" / "base.yaml"),
    )
    assert violations == []


def test_base_as_missing_file_is_ignored_not_crashed():
    # A record with no prior revision (new record) shouldn't error just because
    # --base points at a ref/file that doesn't resolve.
    violations = validate_paths(
        [str(EXAMPLE_RECORD)],
        base=str(BROKEN_DIR / "does-not-exist.yaml"),
    )
    assert violations == []


def test_base_as_git_ref_with_non_ascii_content_is_clean(tmp_path):
    # Regression test: resolve_base()'s `git show` subprocess call used
    # text=True without an explicit encoding, so on a platform whose locale
    # codec isn't UTF-8 (e.g. Windows' default ANSI codepage), any non-ASCII
    # byte in the record -- this repo's own example record has an em dash --
    # got mis-decoded, making the git-ref-loaded "base" record compare
    # unequal to the identical working-tree record and produce a spurious
    # non-monotonic-record-version violation on a record that hadn't
    # actually changed at all. Self-contained (a scratch repo, not this
    # repo's live history) so it doesn't depend on ambient working-tree state.
    repo = tmp_path / "scratch-repo"
    records_dir = repo / "records"
    records_dir.mkdir(parents=True)
    record_text = EXAMPLE_RECORD.read_text(encoding="utf-8")
    assert "—" in record_text  # confirm the fixture actually has an em dash
    (records_dir / "r.yaml").write_text(record_text, encoding="utf-8")

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("-c", "user.name=t", "-c", "user.email=t@example.com", "add", "records/r.yaml")
    git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "init")

    violations = validate_paths([str(records_dir / "r.yaml")], base="HEAD")
    assert violations == []


# --- the plain-language summary (Feature 1) ---------------------------------
#
# The strip is the first thing a non-specialist reads, so the rules on it are
# about what it may not do: exceed the record, run long enough to stop being a
# summary, or state a verdict. The verdict fixture is in the parametrized list
# above; these cover the two rules a fixture cannot express as neatly.


def _record_with_plain_summary(**overrides):
    record = load_record(EXAMPLE_RECORD)
    record["plain_summary"] = {**record["plain_summary"], **overrides}
    return record


def test_plain_summary_word_cap_is_enforced():
    record = _record_with_plain_summary(claimed=" ".join(["word"] * (PLAIN_SUMMARY_MAX_WORDS + 1)))
    rules = {v.rule for v in semantic_violations(record)}
    assert rules == {"plain-summary-too-long"}


def test_plain_summary_at_the_cap_is_allowed():
    record = _record_with_plain_summary(claimed=" ".join(["word"] * PLAIN_SUMMARY_MAX_WORDS))
    assert semantic_violations(record) == []


def test_plain_summary_may_not_hide_open_work():
    # A record carrying open invitations has unfinished work in it by its own
    # account. A summary of that record whose "not checked" line is blank has
    # dropped the part a reader most needs, which is the one way this block
    # could claim more than the record it summarises.
    record = _record_with_plain_summary(not_checked="   ")
    assert record.get("open_invitations"), "fixture must carry open invitations"
    rules = {v.rule for v in semantic_violations(record)}
    assert rules == {"plain-summary-understates-open-work"}


def test_verdict_words_are_refused_only_in_plain_language_blocks():
    # The record-wide rule cannot be widened to these words: a claim's own text
    # may legitimately be "...if and only if the conjecture is false", and a
    # locator quote reproduces whatever the source said. Quoting someone else's
    # verdict is reporting; writing your own is what this project does not do.
    record = load_record(EXAMPLE_RECORD)
    record["claim"]["text"]["value"] = "The conjecture is false for every n > 3."
    assert semantic_violations(record) == []

    record["plain_summary"]["claimed"] = "The conjecture is false for every n > 3."
    assert {v.rule for v in semantic_violations(record)} == {"verdict-language"}


def test_verdict_violation_is_reported_once_per_word():
    record = _record_with_plain_summary(checked="Correct, correct, and correct again; also true.")
    violations = semantic_violations(record)
    assert {v.rule for v in violations} == {"verdict-language"}
    assert len(violations) == 2, [str(v) for v in violations]
