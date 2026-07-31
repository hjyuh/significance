from __future__ import annotations

from pathlib import Path

from significance.diff import diff_records, format_diff_human
from significance.records import load_record

REPO_ROOT = Path(__file__).resolve().parents[1]
BROKEN_DIR = REPO_ROOT / "tests" / "fixtures" / "broken"


def test_diff_identical_records_is_empty():
    a = load_record(BROKEN_DIR / "append-only" / "base.yaml")
    result = diff_records(a, a)
    assert result["changes"] == []
    assert result["staleness_transition"] is None
    assert result["append_only_violations"] == []
    assert "No differences" in format_diff_human(result)


def test_diff_flags_freshness_transition():
    a = load_record(BROKEN_DIR / "append-only" / "base.yaml")
    b = load_record(BROKEN_DIR / "stale-confirmation-rendered-current.yaml")
    result = diff_records(a, b)
    assert result["staleness_transition"] is None  # both are 'current' at the field level
    # observed_source_version changed even though result didn't
    changed_paths = {c["path"] for c in result["changes"]}
    assert "freshness.observed_source_version" in changed_paths


def test_diff_flags_append_only_violations_for_mutated_event():
    a = load_record(BROKEN_DIR / "append-only" / "base.yaml")
    b = load_record(BROKEN_DIR / "append-only" / "mutated-event.yaml")
    result = diff_records(a, b)
    rules = {v["rule"] for v in result["append_only_violations"]}
    assert "history-event-mutated" in rules
    human = format_diff_human(result)
    assert "APPEND-ONLY VIOLATIONS" in human
    assert "history-event-mutated" in human


def test_diff_flags_deleted_event():
    a = load_record(BROKEN_DIR / "append-only" / "base.yaml")
    b = load_record(BROKEN_DIR / "append-only" / "deleted-event.yaml")
    result = diff_records(a, b)
    rules = {v["rule"] for v in result["append_only_violations"]}
    assert "history-event-deleted" in rules


def test_diff_reports_added_evidence_by_id_not_index():
    a = load_record(BROKEN_DIR / "append-only" / "base.yaml")
    b = dict(a)
    b["evidence"] = a["evidence"] + [
        {
            "id": "ev-new",
            "kind": "external_formal_artifact",
            "repo": "https://example.org/x",
            "description": "New evidence.",
            "basis": "author_attestation",
            "asserted_by": "author-as",
            "asserted_at": "2026-07-30T00:00:00Z",
        }
    ]
    result = diff_records(a, b)
    added = [c for c in result["changes"] if c["kind"] == "added"]
    assert any(c["path"] == "evidence[id=ev-new]" for c in added)
    # existing evidence items must not show up as spurious changes
    assert all("ev-lean-formalization" not in c["path"] for c in result["changes"])
