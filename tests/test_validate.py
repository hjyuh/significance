"""Phase 2 tests: `significance validate`'s schema + semantic rules,
covering all ten broken-fixture scenarios named in the design doc.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from significance.validate import validate_paths

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORDS_DIR = REPO_ROOT / "records"
BROKEN_DIR = REPO_ROOT / "tests" / "fixtures" / "broken"


def _rules(violations):
    return {v.rule for v in violations}


def test_valid_record_has_no_violations():
    violations = validate_paths([str(RECORDS_DIR / "2026-sandoval-ramsey-k7.yaml")])
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
        [str(RECORDS_DIR / "2026-sandoval-ramsey-k7.yaml")],
        base=str(BROKEN_DIR / "does-not-exist.yaml"),
    )
    assert violations == []
