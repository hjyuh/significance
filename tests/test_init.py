"""Phase 2: `significance init` produces a schema-valid record from a
canned interactive session, and `write_record` round-trips it to disk."""

from __future__ import annotations

from significance.init import scaffold_record, write_record
from significance.records import load_record, validator

_ANSWERS = [
    "2026-test-example",  # record_id
    "author-x",  # party id
    "n",  # pseudonymous?
    "Test Author",  # name
    "github_identity",  # verification method
    "ghuser123",  # verification identifier
    "n",  # add another party?
    "",  # claim id (default claim-main)
    "Test claim text.",  # claim text value
    "author_attestation",  # claim text basis
    "author-x",  # claim text asserted_by
    "Test scope.",  # claim scope value
    "author_attestation",  # claim scope basis
    "author-x",  # claim scope asserted_by
    "https://example.org/paper",  # manuscript url
    "Test Paper",  # manuscript label
    "8f10a68d54a88afcb6369c01da9ddfb6881d754e5ece210541f8656783692941",  # manuscript sha256
    "",  # retrieved_at (default now)
    "",  # immutable_version_id (skip)
    "current",  # freshness result
    "",  # freshness checked_at (default now)
    "v1",  # observed_source_version
    "v1",  # confirmed_source_version
    "external_formal_artifact",  # evidence kind
    "",  # evidence id (default ev-1)
    "https://github.com/test/repo",  # repo url
    "Test description.",  # description
    "author_attestation",  # basis
    "author-x",  # asserted_by
    "n",  # add another evidence item?
    "LLM used for literature search.",  # AI disclosure value
    "author_attestation",  # AI disclosure basis
    "author-x",  # AI disclosure asserted_by
    "n",  # add an AI-provenance role?
]


def _canned_prompt(answers):
    it = iter(answers)

    def prompt_fn(_question):
        return next(it)

    return prompt_fn


def test_scaffold_record_produces_schema_valid_record():
    record = scaffold_record(_canned_prompt(_ANSWERS))
    errors = list(validator().iter_errors(record))
    assert errors == [], "\n".join(str(e) for e in errors)
    assert record["record_id"] == "2026-test-example"
    assert record["record_version"] == 1
    assert record["freshness"]["result"] == "current"
    assert len(record["evidence"]) == 1
    assert record["ai_provenance"]["roles"] == []


def test_write_record_round_trips(tmp_path):
    record = scaffold_record(_canned_prompt(_ANSWERS))
    records_dir = tmp_path / "records"
    path = write_record(record, records_dir)

    assert path == records_dir / "2026-test-example.yaml"
    reloaded = load_record(path)
    assert reloaded["record_id"] == record["record_id"]
    errors = list(validator().iter_errors(reloaded))
    assert errors == []
