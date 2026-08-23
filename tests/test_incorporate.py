from pathlib import Path

import pytest
from ruamel.yaml import YAML

from significance.incorporate import incorporate_attestation

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "synthetic-ramsey-k7.yaml"


def _fixture_record(tmp_path: Path) -> tuple[Path, dict]:
    yaml = YAML(typ="safe")
    record = yaml.load(EXAMPLE.read_text(encoding="utf-8"))
    record["parties"]["reviewer"] = {
        "name": "Scoped Reviewer",
        "verification_method": {"kind": "github_identity"},
    }
    record["open_invitations"][0]["task_id"] = "task-one"
    path = tmp_path / "record.yaml"
    writer = YAML()
    with path.open("w", encoding="utf-8") as handle:
        writer.dump(record, handle)
    return path, record


def _attestation(tmp_path: Path, record: dict, **changes) -> Path:
    value = {
        "id": "att-task-one",
        "task_id": "task-one",
        "reviewer": "reviewer",
        "scope": record["open_invitations"][0]["target"],
        "manuscript_sha256": record["manuscript"]["sha256"],
        "asserted_at": "2026-08-20T12:00:00Z",
        "method": "read",
        "finding": "I followed the stated passage and recorded the definitions used.",
    }
    value.update(changes)
    path = tmp_path / "attestation.yaml"
    yaml = YAML()
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(value, handle)
    return path


def test_incorporation_marks_task_done_and_appends_history(tmp_path):
    _, record = _fixture_record(tmp_path)
    attestation_path = _attestation(tmp_path, record)
    result = incorporate_attestation(attestation_path, record["record_id"], tmp_path)
    updated = YAML(typ="safe").load(result.read_text(encoding="utf-8"))
    assert updated["attestations"][0]["id"] == "att-task-one"
    assert updated["open_invitations"][0]["status"] == "done"
    assert updated["open_invitations"][0]["done_ref"] == "att-task-one"
    assert updated["history"][-1]["type"] == "attestation_added"
    assert updated["record_version"] == record["record_version"] + 1


def test_incorporation_rejects_hash_mismatch(tmp_path):
    _, record = _fixture_record(tmp_path)
    attestation_path = _attestation(tmp_path, record, manuscript_sha256="0" * 64)
    with pytest.raises(ValueError, match="does not match"):
        incorporate_attestation(attestation_path, record["record_id"], tmp_path)


def test_incorporation_rejects_verdict_language(tmp_path):
    _, record = _fixture_record(tmp_path)
    attestation_path = _attestation(tmp_path, record, finding="The proof is correct.")
    with pytest.raises(ValueError, match="verdict-language"):
        incorporate_attestation(attestation_path, record["record_id"], tmp_path)
