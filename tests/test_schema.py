"""Phase 1 schema-level tests.

Covers: the schema itself is valid Draft 2020-12; the example record in
records/ validates cleanly; and each deliberately broken fixture in
tests/fixtures/broken/ fails validation for the reason its filename claims.
Cross-record semantic rules (uniqueness, append-only history, etc.) are
Phase 2 CLI concerns and are not exercised here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from significance.records import load_record, load_schema, validator

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORDS_DIR = REPO_ROOT / "records"
BROKEN_DIR = REPO_ROOT / "tests" / "fixtures" / "broken"


def test_schema_itself_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(load_schema())


def test_schema_forbids_additional_top_level_properties():
    schema = load_schema()
    assert schema.get("additionalProperties") is False


@pytest.mark.parametrize(
    "record_path", sorted(RECORDS_DIR.glob("*.yaml")), ids=lambda p: p.name
)
def test_example_records_are_valid(record_path):
    record = load_record(record_path)
    errors = list(validator().iter_errors(record))
    assert errors == [], "\n".join(str(e) for e in errors)


def _prose_strings(node):
    """Yield human-authored prose values: `text`/`value` strings anywhere
    in the record. Field *names* like `verified_at` (an identity check
    timestamp, per invariant on parties) are a distinct concept from
    claim-truth verification and are not in scope here."""
    if isinstance(node, dict):
        for key, val in node.items():
            if key in ("text", "value") and isinstance(val, str):
                yield val
            yield from _prose_strings(val)
    elif isinstance(node, list):
        for item in node:
            yield from _prose_strings(item)


def test_example_record_has_no_forbidden_language():
    # Invariant 1: no rendered/authored prose may assert verified/proven truth.
    record = load_record(RECORDS_DIR / "2026-sandoval-ramsey-k7.yaml")
    for prose in _prose_strings(record):
        lowered = prose.lower()
        assert "verified" not in lowered, prose
        assert "proven" not in lowered, prose


BROKEN_FIXTURES = [
    "unattributed-assertion.yaml",
    "missing-manuscript-hash.yaml",
    "correspondence-machine-asserted.yaml",
    "bare-result-passed-no-receipt.yaml",
]
# The remaining broken-fixture cases named in the design doc (stale
# confirmation rendered current, mutated historical event, deleted event id,
# non-monotonic record_version, duplicate record_id) require comparing a
# record against a base-branch version or against sibling records in the
# repository. A single record's JSON Schema cannot express those checks;
# they belong to `significance validate` in Phase 2.


@pytest.mark.parametrize("fixture_name", BROKEN_FIXTURES)
def test_broken_fixture_fails_validation(fixture_name):
    record = load_record(BROKEN_DIR / fixture_name)
    assert not validator().is_valid(record), (
        f"{fixture_name} was expected to fail schema validation but passed"
    )
